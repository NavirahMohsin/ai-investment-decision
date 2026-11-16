"""Model evaluation and backtesting service.

Builds chronologically ordered evaluation datasets, scores registered models
out-of-sample (with embargo to prevent look-ahead), supports walk-forward
scoring of frozen models, compares models on a shared dataset, and runs
persisted strategy backtests via BacktestEngine.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import BacktestRun, Company, DailyMarketData
from app.ml.backtesting import BacktestConfig, BacktestEngine
from app.ml.evaluation import ClassificationEvaluator, EvaluationConfig, FinancialEvaluator, TemporalSplitter
from app.ml.feature_engineering import DatasetGenerator, FeatureConfig
from app.ml.model_server import ModelServer
from app.ml.prediction_targets import TargetConfig, TargetGenerator
from app.services.indicators import IndicatorParameters

logger = logging.getLogger(__name__)

EVAL_DISCLAIMER = (
    "Metrics are computed on chronologically held-out data with an embargo equal "
    "to the prediction horizon to reduce look-ahead bias. These results are for "
    "research only and do not constitute investment advice. Never invent or "
    "extrapolate unavailable metrics."
)

BACKTEST_DISCLAIMER = (
    "Backtest results are simulated and include modelled commission and slippage. "
    "Past simulated performance is not indicative of future results and does not "
    "constitute investment advice."
)


def _normalize_label(value: Any) -> str:
    """Normalize target/prediction labels to lowercase class names."""
    if value is None:
        return "neutral"
    if hasattr(value, "value"):
        value = value.value
    text = str(value).strip().lower()
    mapping = {
        "positive": "positive",
        "negative": "negative",
        "neutral": "neutral",
        "1": "positive",
        "-1": "negative",
        "0": "neutral",
    }
    return mapping.get(text, text)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
        if np.isnan(out) or np.isinf(out):
            return None
        return out
    except (TypeError, ValueError):
        return None


class ModelEvaluationService:
    """Evaluate and backtest registered ML models against market history."""

    def __init__(
        self,
        model_server: ModelServer,
        feature_config: FeatureConfig | None = None,
        indicator_params: IndicatorParameters | None = None,
        target_config: TargetConfig | None = None,
    ) -> None:
        self.model_server = model_server
        self.feature_config = feature_config or FeatureConfig()
        self.indicator_params = indicator_params or IndicatorParameters()
        self.target_config = target_config or TargetConfig()
        self.dataset_gen = DatasetGenerator(self.feature_config, self.indicator_params)
        self.target_gen = TargetGenerator(self.target_config)

    # ── Data loading ─────────────────────────────────────────────────────────

    def _load_ohlcv(
        self,
        db: Session,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 2500,
    ) -> tuple[Company, pd.DataFrame]:
        company = db.query(Company).filter(Company.symbol == symbol.strip().upper()).first()
        if not company:
            raise ValueError(f"Company not found: {symbol}")

        query = db.query(DailyMarketData).filter(DailyMarketData.company_id == company.id)
        if start_date:
            query = query.filter(DailyMarketData.trading_date >= start_date)
        if end_date:
            query = query.filter(DailyMarketData.trading_date <= end_date)

        rows = (
            query.order_by(DailyMarketData.trading_date.desc())
            .limit(limit)
            .all()
        )
        rows = list(reversed(rows))
        if len(rows) < 60:
            raise ValueError(
                f"Insufficient market history for {symbol}: need at least 60 bars, found {len(rows)}"
            )

        df = pd.DataFrame(
            [
                {
                    "trading_date": r.trading_date,
                    "open": float(r.open) if r.open is not None else np.nan,
                    "high": float(r.high) if r.high is not None else np.nan,
                    "low": float(r.low) if r.low is not None else np.nan,
                    "close": float(r.close) if r.close is not None else np.nan,
                    "volume": int(r.volume) if r.volume is not None else 0,
                    "symbol": company.symbol,
                }
                for r in rows
            ]
        )
        return company, df

    def _build_aligned_dataset(
        self,
        ohlcv: pd.DataFrame,
        model_feature_names: list[str],
        horizon_days: int,
    ) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series]:
        """Return chronologically ordered X, y, prices, dates with no target leakage."""
        features_df = self.dataset_gen.generate_features(ohlcv)
        if "symbol" not in features_df.columns:
            features_df = features_df.copy()
            features_df["symbol"] = ohlcv["symbol"].iloc[0]

        targets_df = self.target_gen.generate(ohlcv)
        targets_df = targets_df.copy()
        targets_df["symbol"] = ohlcv["symbol"].iloc[0]

        # Normalize enum targets to lowercase strings
        target_col = f"{horizon_days}_day_target"
        if target_col not in targets_df.columns:
            raise ValueError(f"Target column {target_col} not available")
        targets_df[target_col] = targets_df[target_col].map(_normalize_label)

        merged = self.dataset_gen.merge_features_and_targets(features_df, targets_df)
        merged = merged[merged["data_available"] == True].copy()  # noqa: E712
        merged = merged.sort_values("trading_date").reset_index(drop=True)

        # Align to model feature set; missing columns become NaN then dropped
        available = [c for c in model_feature_names if c in merged.columns]
        missing = [c for c in model_feature_names if c not in merged.columns]
        if missing:
            raise ValueError(
                f"Evaluation features missing from dataset: {missing[:8]}"
                + ("..." if len(missing) > 8 else "")
            )

        X = merged[available].apply(pd.to_numeric, errors="coerce")
        y = merged[target_col].map(_normalize_label)

        close_map = {
            (d if isinstance(d, date) else pd.to_datetime(d).date()): c
            for d, c in zip(ohlcv["trading_date"], ohlcv["close"])
        }
        if "close" in merged.columns:
            prices = pd.to_numeric(merged["close"], errors="coerce")
        else:
            prices = merged["trading_date"].map(
                lambda d: close_map.get(d if isinstance(d, date) else pd.to_datetime(d).date())
            )
            prices = pd.to_numeric(prices, errors="coerce")

        dates = pd.to_datetime(merged["trading_date"])

        valid = X.notna().all(axis=1) & y.notna() & prices.notna()
        X = X.loc[valid].reset_index(drop=True)
        y = y.loc[valid].reset_index(drop=True)
        prices = prices.loc[valid].reset_index(drop=True)
        dates = dates.loc[valid].reset_index(drop=True)

        if len(X) < 40:
            raise ValueError(
                f"Insufficient aligned samples for evaluation after cleaning: {len(X)}"
            )
        return X, y, prices, dates

    def _chronological_holdout(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        prices: pd.Series,
        dates: pd.Series,
        horizon_days: int,
        test_size: float = 0.2,
    ) -> dict[str, Any]:
        """Split with embargo equal to horizon to reduce leakage."""
        n = len(X)
        train_end = int(n * (1.0 - test_size))
        embargo = max(horizon_days, 1)
        test_start = min(train_end + embargo, n)
        if test_start >= n or train_end < 20:
            raise ValueError(
                f"Cannot form a valid holdout split (n={n}, train_end={train_end}, "
                f"embargo={embargo}). Need more history."
            )
        return {
            "X_train": X.iloc[:train_end],
            "y_train": y.iloc[:train_end],
            "X_test": X.iloc[test_start:],
            "y_test": y.iloc[test_start:],
            "prices_test": prices.iloc[test_start:],
            "dates_test": dates.iloc[test_start:],
            "train_start": dates.iloc[0].date(),
            "train_end": dates.iloc[train_end - 1].date(),
            "test_start": dates.iloc[test_start].date(),
            "test_end": dates.iloc[-1].date(),
            "embargo_days": embargo,
            "n_train": train_end,
            "n_test": n - test_start,
        }

    def _predict_frame(
        self,
        model: Any,
        scaler: Any,
        metadata: Any,
        X: pd.DataFrame,
    ) -> tuple[np.ndarray, np.ndarray | None]:
        features = X.values.astype(float)
        if scaler is not None:
            features = scaler.transform(features)
        y_pred_idx = model.predict(features)
        classes = list(getattr(metadata, "classes", []) or [])
        if classes:
            y_pred = np.array([
                _normalize_label(classes[int(i)] if int(i) < len(classes) else i)
                for i in y_pred_idx
            ])
        else:
            y_pred = np.array([_normalize_label(v) for v in y_pred_idx])

        y_proba = None
        if hasattr(model, "predict_proba"):
            try:
                y_proba = model.predict_proba(features)
            except Exception:
                y_proba = None
        return y_pred, y_proba

    def _financial_from_predictions(
        self,
        y_pred: np.ndarray,
        prices: pd.Series,
    ) -> dict[str, Any]:
        if len(prices) < 2:
            return {
                "total_return": None,
                "annual_return": None,
                "max_drawdown": None,
                "sharpe_ratio": None,
                "win_rate": None,
                "profit_factor": None,
                "num_trades": 0,
            }

        returns = prices.pct_change().fillna(0.0)
        # Long when positive, flat/short-neutral otherwise for metric estimation
        position = pd.Series(
            [1.0 if _normalize_label(p) == "positive" else (
                -1.0 if _normalize_label(p) == "negative" else 0.0
            ) for p in y_pred],
            index=returns.index,
        )
        # Shift positions by 1 to avoid same-bar look-ahead
        strategy_returns = (position.shift(1).fillna(0.0) * returns)
        trades = (position != 0).astype(int)
        metrics = FinancialEvaluator().evaluate(strategy_returns, trades)
        return {
            "total_return": round(metrics.total_return, 4),
            "annual_return": round(metrics.annual_return, 4),
            "max_drawdown": round(metrics.max_drawdown, 4),
            "sharpe_ratio": round(metrics.sharpe_ratio, 4),
            "win_rate": round(metrics.win_rate, 4),
            "profit_factor": round(metrics.profit_factor, 4),
            "num_trades": metrics.num_trades,
        }

    def _metrics_payload(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray | None,
        prices: pd.Series,
        classes: list[str],
    ) -> dict[str, Any]:
        y_true_n = np.array([_normalize_label(v) for v in y_true])
        y_pred_n = np.array([_normalize_label(v) for v in y_pred])
        label_set = sorted(set(y_true_n) | set(y_pred_n) | set(_normalize_label(c) for c in classes))
        class_metrics = ClassificationEvaluator.evaluate(y_true_n, y_pred_n, y_proba=None)
        # Recompute confusion with stable label order
        from sklearn.metrics import confusion_matrix, classification_report

        cm = confusion_matrix(y_true_n, y_pred_n, labels=label_set)
        report = classification_report(
            y_true_n, y_pred_n, labels=label_set, output_dict=True, zero_division=0
        )
        roc_auc = None
        if y_proba is not None and len(label_set) >= 2:
            try:
                from sklearn.metrics import roc_auc_score
                from sklearn.preprocessing import LabelEncoder

                enc = LabelEncoder()
                enc.fit(label_set)
                y_true_enc = enc.transform(y_true_n)
                # Align probability columns to label_set if possible
                if y_proba.shape[1] == len(classes):
                    class_norm = [_normalize_label(c) for c in classes]
                    aligned = np.zeros((len(y_true_n), len(label_set)))
                    for i, lbl in enumerate(label_set):
                        if lbl in class_norm:
                            aligned[:, i] = y_proba[:, class_norm.index(lbl)]
                    roc_auc = float(
                        roc_auc_score(y_true_enc, aligned, multi_class="ovr", average="macro")
                    )
            except Exception as exc:
                logger.debug("ROC-AUC unavailable: %s", exc)
                roc_auc = None

        return {
            "metrics": {
                "accuracy": round(float(class_metrics.accuracy), 6),
                "precision": round(float(class_metrics.precision), 6),
                "recall": round(float(class_metrics.recall), 6),
                "f1": round(float(class_metrics.f1), 6),
                "roc_auc": round(roc_auc, 6) if roc_auc is not None else None,
                "sample_count": int(len(y_true_n)),
            },
            "confusion_matrix": cm.tolist(),
            "confusion_matrix_labels": label_set,
            "class_metrics": report,
            "financial_metrics": self._financial_from_predictions(y_pred_n, prices),
        }

    # ── Public API ───────────────────────────────────────────────────────────

    def evaluate_model(
        self,
        db: Session,
        model_id: str,
        symbol: str,
        horizon_days: int = 1,
        version: str = "latest",
        evaluation_type: Literal["holdout_oos", "walk_forward"] = "holdout_oos",
        test_size: float = 0.2,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        if horizon_days not in (1, 5, 20):
            raise ValueError("horizon_days must be 1, 5, or 20")
        if not (0.1 <= test_size <= 0.5):
            raise ValueError("test_size must be between 0.1 and 0.5")

        model, metadata, scaler = self.model_server.load_model(model_id, version)
        feature_names = list(metadata.feature_names or [])
        if not feature_names:
            raise ValueError(f"Model {model_id} has no feature_names metadata")

        _, ohlcv = self._load_ohlcv(db, symbol, start_date, end_date)
        X, y, prices, dates = self._build_aligned_dataset(ohlcv, feature_names, horizon_days)

        if evaluation_type == "holdout_oos":
            split = self._chronological_holdout(X, y, prices, dates, horizon_days, test_size)
            y_pred, y_proba = self._predict_frame(model, scaler, metadata, split["X_test"])
            payload = self._metrics_payload(
                split["y_test"].values, y_pred, y_proba, split["prices_test"], list(metadata.classes or [])
            )
            return {
                "model_id": metadata.model_id,
                "model_type": metadata.model_type,
                "version": metadata.version,
                "symbol": symbol.strip().upper(),
                "horizon_days": horizon_days,
                "evaluation_type": "holdout_oos",
                **payload,
                "validation_window": {
                    "train_start": split["train_start"].isoformat(),
                    "train_end": split["train_end"].isoformat(),
                    "test_start": split["test_start"].isoformat(),
                    "test_end": split["test_end"].isoformat(),
                    "embargo_days": split["embargo_days"],
                    "n_train": split["n_train"],
                    "n_test": split["n_test"],
                    "test_size": test_size,
                },
                "disclaimer": EVAL_DISCLAIMER,
            }

        # Walk-forward scoring of the frozen model on sequential OOS windows
        config = EvaluationConfig(train_size=0.6, val_size=0.2, test_size=0.2, walk_forward_step=max(20, horizon_days * 4))
        splitter = TemporalSplitter(config)
        # Use TemporalSplitter.split for initial windows via walk_forward_splits
        # Build a synthetic DataFrame with DatetimeIndex for splitter compatibility
        X_idx = X.copy()
        X_idx.index = pd.DatetimeIndex(dates)
        y_idx = y.copy()
        y_idx.index = pd.DatetimeIndex(dates)
        prices_idx = prices.copy()
        prices_idx.index = pd.DatetimeIndex(dates)

        folds = splitter.walk_forward_splits(X_idx, y_idx)
        if not folds:
            raise ValueError("Unable to create walk-forward folds with available history")

        fold_metrics = []
        all_true: list[str] = []
        all_pred: list[str] = []
        all_prices: list[float] = []

        for fold_i, ((_X_train, _y_train), (X_val, y_val)) in enumerate(folds):
            # Embargo: drop first horizon_days of validation relative to train end
            if len(X_val) <= horizon_days:
                continue
            X_val_e = X_val.iloc[horizon_days:]
            y_val_e = y_val.iloc[horizon_days:]
            prices_val = prices_idx.loc[X_val_e.index]
            y_pred, y_proba = self._predict_frame(model, scaler, metadata, X_val_e.reset_index(drop=True))
            fold_payload = self._metrics_payload(
                y_val_e.values, y_pred, y_proba, prices_val.reset_index(drop=True), list(metadata.classes or [])
            )
            fold_metrics.append({
                "fold": fold_i + 1,
                "start": X_val_e.index[0].date().isoformat(),
                "end": X_val_e.index[-1].date().isoformat(),
                "n_samples": len(y_val_e),
                "accuracy": fold_payload["metrics"]["accuracy"],
                "f1": fold_payload["metrics"]["f1"],
            })
            all_true.extend([_normalize_label(v) for v in y_val_e.values])
            all_pred.extend(list(y_pred))
            all_prices.extend(list(prices_val.values))

        if not all_true:
            raise ValueError("Walk-forward evaluation produced no valid folds")

        aggregate = self._metrics_payload(
            np.array(all_true),
            np.array(all_pred),
            None,
            pd.Series(all_prices),
            list(metadata.classes or []),
        )
        return {
            "model_id": metadata.model_id,
            "model_type": metadata.model_type,
            "version": metadata.version,
            "symbol": symbol.strip().upper(),
            "horizon_days": horizon_days,
            "evaluation_type": "walk_forward",
            **aggregate,
            "validation_window": {
                "folds": fold_metrics,
                "n_folds": len(fold_metrics),
                "embargo_days": horizon_days,
                "note": (
                    "Walk-forward scores a frozen registered model on sequential "
                    "out-of-sample windows (no fold retraining). This avoids "
                    "look-ahead but is not identical to retrain-each-fold validation."
                ),
            },
            "disclaimer": EVAL_DISCLAIMER,
        }

    def compare_models(
        self,
        db: Session,
        model_ids: list[str],
        symbol: str,
        horizon_days: int = 1,
        version: str = "latest",
        test_size: float = 0.2,
    ) -> dict[str, Any]:
        if len(model_ids) < 2:
            raise ValueError("Provide at least two model_ids to compare")
        if len(model_ids) > 8:
            raise ValueError("Compare at most 8 models at once")

        results = []
        errors = []
        for mid in model_ids:
            try:
                result = self.evaluate_model(
                    db=db,
                    model_id=mid,
                    symbol=symbol,
                    horizon_days=horizon_days,
                    version=version,
                    evaluation_type="holdout_oos",
                    test_size=test_size,
                )
                results.append(result)
            except Exception as exc:
                logger.warning("Comparison skipped for %s: %s", mid, exc)
                errors.append({"model_id": mid, "error": str(exc)})

        if len(results) < 2:
            raise ValueError(
                "Need at least two successful evaluations on a compatible dataset. "
                + (f"Errors: {errors}" if errors else "")
            )

        # Ensure comparable windows — warn if test windows differ
        windows = {
            (r["validation_window"]["test_start"], r["validation_window"]["test_end"], r["validation_window"]["n_test"])
            for r in results
        }
        comparable = len(windows) == 1

        comparison_table = []
        for r in results:
            comparison_table.append({
                "model_id": r["model_id"],
                "model_type": r["model_type"],
                "version": r["version"],
                "accuracy": r["metrics"]["accuracy"],
                "precision": r["metrics"]["precision"],
                "recall": r["metrics"]["recall"],
                "f1": r["metrics"]["f1"],
                "roc_auc": r["metrics"].get("roc_auc"),
                "total_return": (r.get("financial_metrics") or {}).get("total_return"),
                "max_drawdown": (r.get("financial_metrics") or {}).get("max_drawdown"),
                "sharpe_ratio": (r.get("financial_metrics") or {}).get("sharpe_ratio"),
                "n_test": r["validation_window"]["n_test"],
            })

        comparison_table.sort(key=lambda row: (row["f1"] is not None, row["f1"] or 0), reverse=True)
        benchmark = comparison_table[0]["model_id"] if comparison_table else None

        return {
            "symbol": symbol.strip().upper(),
            "horizon_days": horizon_days,
            "comparable_dataset": comparable,
            "models": [
                {
                    "model_id": r["model_id"],
                    "model_type": r["model_type"],
                    "version": r["version"],
                    "metrics": r["metrics"],
                    "financial_metrics": r.get("financial_metrics"),
                    "validation_window": r["validation_window"],
                }
                for r in results
            ],
            "benchmark_model_id": benchmark,
            "comparison_table": comparison_table,
            "errors": errors,
            "disclaimer": EVAL_DISCLAIMER,
        }

    def run_backtest(
        self,
        db: Session,
        symbol: str,
        model_id: str = "latest",
        version: str = "latest",
        horizon_days: int = 1,
        initial_capital: float = 100000.0,
        commission: float = 0.001,
        slippage: float = 0.0005,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        if horizon_days not in (1, 5, 20):
            raise ValueError("horizon_days must be 1, 5, or 20")

        # Resolve model
        if not model_id or model_id == "latest":
            models = self.model_server.list_models()
            if not models:
                raise ValueError("No trained models available")
            best = max(models, key=lambda m: m.get("accuracy") or 0)
            model_id = best["model_id"]
            version = best.get("version") or "latest"

        model, metadata, scaler = self.model_server.load_model(model_id, version)
        feature_names = list(metadata.feature_names or [])
        if not feature_names:
            raise ValueError(f"Model {model_id} has no feature_names metadata")

        company, ohlcv = self._load_ohlcv(db, symbol, start_date, end_date)
        X, y, prices, dates = self._build_aligned_dataset(ohlcv, feature_names, horizon_days)

        # Use holdout region only for backtest to avoid in-sample optimism
        split = self._chronological_holdout(X, y, prices, dates, horizon_days, test_size=0.3)
        X_bt = split["X_test"]
        prices_bt = split["prices_test"]
        dates_bt = split["dates_test"]

        y_pred, _ = self._predict_frame(model, scaler, metadata, X_bt)
        signals = pd.Series(
            [
                1 if _normalize_label(p) == "positive"
                else (-1 if _normalize_label(p) == "negative" else 0)
                for p in y_pred
            ],
            index=pd.DatetimeIndex(dates_bt),
        )
        price_series = pd.Series(prices_bt.values, index=pd.DatetimeIndex(dates_bt))

        engine = BacktestEngine(
            BacktestConfig(
                initial_capital=initial_capital,
                commission=commission,
                slippage=slippage,
            )
        )
        result = engine.backtest(
            price_series,
            signals,
            strategy_name=f"ML_{metadata.model_type}_{horizon_days}D",
        )

        backtest_id = str(uuid.uuid4())
        equity_curve = [
            {"date": (idx.date().isoformat() if hasattr(idx, "date") else str(idx)), "value": float(val)}
            for idx, val in result.equity_curve.items()
        ]
        trades = [
            {
                "date": t.date.isoformat(),
                "direction": t.direction,
                "price": round(float(t.price), 4),
                "quantity": round(float(t.quantity), 6),
                "value": round(float(t.value), 4),
                "commission": round(float(t.commission), 4),
            }
            for t in result.trades
        ]

        payload = {
            "backtest_id": backtest_id,
            "symbol": company.symbol,
            "model_id": metadata.model_id,
            "strategy_name": result.strategy_name,
            "start_date": result.start_date.isoformat(),
            "end_date": result.end_date.isoformat(),
            "initial_capital": float(result.initial_capital),
            "final_value": round(float(result.final_value), 4),
            "total_return": round(float(result.total_return), 6),
            "annual_return": round(float(result.annual_return), 6),
            "max_drawdown": round(float(result.max_drawdown), 6),
            "sharpe_ratio": round(float(result.sharpe_ratio), 4) if result.sharpe_ratio is not None else None,
            "win_rate": round(float(result.win_rate), 4) if result.win_rate is not None else None,
            "profit_factor": round(float(result.profit_factor), 4) if result.profit_factor is not None else None,
            "num_trades": int(result.num_trades),
            "equity_curve": equity_curve,
            "trades": trades,
            "disclaimer": BACKTEST_DISCLAIMER,
        }

        # Persist
        try:
            row = BacktestRun(
                backtest_id=backtest_id,
                ticker=company.symbol,
                model_id=metadata.model_id,
                strategy_name=result.strategy_name,
                start_date=result.start_date,
                end_date=result.end_date,
                initial_capital=Decimal(str(round(result.initial_capital, 4))),
                final_value=Decimal(str(round(result.final_value, 4))),
                total_return=Decimal(str(round(result.total_return, 6))),
                annual_return=Decimal(str(round(result.annual_return, 6))),
                max_drawdown=Decimal(str(round(result.max_drawdown, 6))),
                sharpe_ratio=Decimal(str(round(result.sharpe_ratio, 4))) if result.sharpe_ratio is not None else None,
                win_rate=Decimal(str(round(result.win_rate, 4))) if result.win_rate is not None else None,
                profit_factor=Decimal(str(round(result.profit_factor, 4))) if result.profit_factor is not None else None,
                num_trades=int(result.num_trades),
                parameters={
                    "horizon_days": horizon_days,
                    "commission": commission,
                    "slippage": slippage,
                    "version": metadata.version,
                    "evaluation_window": {
                        "test_start": split["test_start"].isoformat(),
                        "test_end": split["test_end"].isoformat(),
                        "embargo_days": split["embargo_days"],
                    },
                },
                equity_curve=equity_curve,
                trades=trades,
            )
            db.add(row)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to persist backtest %s: %s", backtest_id, exc)

        return payload

    def list_backtests(
        self,
        db: Session,
        symbol: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        query = db.query(BacktestRun)
        if symbol:
            query = query.filter(BacktestRun.ticker == symbol.strip().upper())
        total = query.count()
        rows = (
            query.order_by(BacktestRun.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        items = []
        for r in rows:
            items.append({
                "backtest_id": r.backtest_id,
                "symbol": r.ticker,
                "model_id": r.model_id,
                "strategy_name": r.strategy_name,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
                "initial_capital": float(r.initial_capital),
                "final_value": float(r.final_value),
                "total_return": float(r.total_return),
                "annual_return": float(r.annual_return),
                "max_drawdown": float(r.max_drawdown),
                "sharpe_ratio": float(r.sharpe_ratio) if r.sharpe_ratio is not None else None,
                "win_rate": float(r.win_rate) if r.win_rate is not None else None,
                "profit_factor": float(r.profit_factor) if r.profit_factor is not None else None,
                "num_trades": r.num_trades,
                "equity_curve": r.equity_curve or [],
                "trades": r.trades or [],
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "disclaimer": BACKTEST_DISCLAIMER,
            })
        return items, total

    def get_backtest(self, db: Session, backtest_id: str) -> dict[str, Any]:
        row = db.query(BacktestRun).filter(BacktestRun.backtest_id == backtest_id).first()
        if not row:
            raise ValueError(f"Backtest not found: {backtest_id}")
        return {
            "backtest_id": row.backtest_id,
            "symbol": row.ticker,
            "model_id": row.model_id,
            "strategy_name": row.strategy_name,
            "start_date": row.start_date.isoformat(),
            "end_date": row.end_date.isoformat(),
            "initial_capital": float(row.initial_capital),
            "final_value": float(row.final_value),
            "total_return": float(row.total_return),
            "annual_return": float(row.annual_return),
            "max_drawdown": float(row.max_drawdown),
            "sharpe_ratio": float(row.sharpe_ratio) if row.sharpe_ratio is not None else None,
            "win_rate": float(row.win_rate) if row.win_rate is not None else None,
            "profit_factor": float(row.profit_factor) if row.profit_factor is not None else None,
            "num_trades": row.num_trades,
            "equity_curve": row.equity_curve or [],
            "trades": row.trades or [],
            "parameters": row.parameters,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "disclaimer": BACKTEST_DISCLAIMER,
        }
