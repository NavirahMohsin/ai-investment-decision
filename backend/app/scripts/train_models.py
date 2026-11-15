"""Train and save ML models for stock price prediction.

This script:
1. Loads historical market data for Indian stocks
2. Generates features and prediction targets
3. Trains 4 models: LogisticRegression, RandomForest, XGBoost, LightGBM
4. Evaluates models with cross-validation
5. Saves trained models to disk with metadata

Usage:
    python -m app.scripts.train_models [--symbol SYMBOL] [--min-date DATE] [--max-date DATE]

Examples:
    # Train on all available symbols
    python -m app.scripts.train_models
    
    # Train on specific symbol
    python -m app.scripts.train_models --symbol RELIANCE
    
    # Train on specific date range
    python -m app.scripts.train_models --min-date 2023-01-01 --max-date 2025-01-01
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np
from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models import Company, DailyMarketData
from app.ml.prediction_targets import TargetConfig, TargetGenerator
from app.ml.feature_engineering import FeatureConfig, DatasetGenerator
from app.ml.models import ModelConfig, ModelTrainer, ModelType, ModelComparator
from app.ml.model_server import ModelServer, ModelMetadata, ModelStatus
from sklearn.preprocessing import StandardScaler


logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def load_ohlcv_from_db(
    symbol: Optional[str] = None,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None,
) -> dict[str, pd.DataFrame]:
    """Load OHLCV data from database.
    
    Args:
        symbol: Specific symbol to load, or None for all
        min_date: Earliest date to include
        max_date: Latest date to include
        
    Returns:
        Dictionary mapping symbol to OHLCV DataFrame
    """
    with SessionLocal() as db:
        # Get companies
        query = select(Company)
        if symbol:
            query = query.where(Company.symbol == symbol)
        
        companies = db.scalars(query).all()
        
        if not companies:
            raise ValueError(f"No companies found" + (f" with symbol {symbol}" if symbol else ""))
        
        result = {}
        
        for company in companies:
            logger.info(f"Loading data for {company.symbol}")
            
            # Query market data
            mkt_query = select(DailyMarketData).where(
                DailyMarketData.company_id == company.id
            ).order_by(DailyMarketData.trading_date)
            
            if min_date:
                mkt_query = mkt_query.where(DailyMarketData.trading_date >= min_date)
            if max_date:
                mkt_query = mkt_query.where(DailyMarketData.trading_date <= max_date)
            
            records = db.scalars(mkt_query).all()
            
            if not records:
                logger.warning(f"No data for {company.symbol}")
                continue
            
            # Convert to DataFrame
            data = []
            for row in records:
                data.append({
                    "trading_date": row.trading_date,
                    "open": float(row.open),
                    "high": float(row.high),
                    "low": float(row.low),
                    "close": float(row.close),
                    "adjusted_close": float(row.adjusted_close or row.close),
                    "volume": int(row.volume) if row.volume else 0,
                })
            
            df = pd.DataFrame(data)
            logger.info(f"  Loaded {len(df)} trading days for {company.symbol}")
            result[company.symbol] = df
        
        return result


def aggregate_data(ohlcv_dict: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Aggregate data from multiple symbols.
    
    Args:
        ohlcv_dict: Dictionary of symbol -> OHLCV DataFrame
        
    Returns:
        Combined DataFrame with symbol column
    """
    # Concatenate without symbol column for now
    # (features will be generated per-symbol, then combined)
    dfs = []
    
    for symbol, df in ohlcv_dict.items():
        df_copy = df.copy()
        df_copy["symbol"] = symbol
        dfs.append(df_copy)
    
    combined = pd.concat(dfs, ignore_index=True)
    combined = combined.sort_values(["symbol", "trading_date"]).reset_index(drop=True)
    
    logger.info(f"Aggregated data: {len(combined)} total records")
    
    return combined


def process_data_by_symbol(
    ohlcv_dict: dict[str, pd.DataFrame]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Process features and targets for each symbol separately, then combine.
    
    Args:
        ohlcv_dict: Dictionary of symbol -> OHLCV DataFrame
        
    Returns:
        Tuple of (combined features DataFrame, combined targets DataFrame)
    """
    all_features = []
    all_targets = []
    
    dataset_gen = DatasetGenerator()
    target_gen = TargetGenerator(TargetConfig())
    
    for symbol, ohlcv_df in ohlcv_dict.items():
        logger.info(f"Processing features/targets for {symbol}...")
        
        # Generate features for this symbol
        try:
            features_df = dataset_gen.generate_features(ohlcv_df)
            # Ensure trading_date is consistent type
            if 'trading_date' in features_df.columns:
                features_df['trading_date'] = pd.to_datetime(features_df['trading_date']).dt.date
            all_features.append(features_df)
        except Exception as e:
            logger.warning(f"Failed to generate features for {symbol}: {e}")
            continue
        
        # Generate targets for this symbol
        try:
            targets_df = target_gen.generate(ohlcv_df)
            # Ensure trading_date is consistent type
            if 'trading_date' in targets_df.columns:
                targets_df['trading_date'] = pd.to_datetime(targets_df['trading_date']).dt.date
            all_targets.append(targets_df)
        except Exception as e:
            logger.warning(f"Failed to generate targets for {symbol}: {e}")
            continue
    
    # Combine all features and targets
    combined_features = pd.concat(all_features, ignore_index=True)
    combined_targets = pd.concat(all_targets, ignore_index=True)
    
    # Ensure trading_date columns are date type for both
    combined_features['trading_date'] = pd.to_datetime(combined_features['trading_date']).dt.date
    combined_targets['trading_date'] = pd.to_datetime(combined_targets['trading_date']).dt.date
    
    logger.info(f"Combined features shape: {combined_features.shape}")
    logger.info(f"Combined targets shape: {combined_targets.shape}")
    
    return combined_features, combined_targets


def train_models_on_data(
    features_df: pd.DataFrame,
    targets_df: pd.DataFrame,
    horizon_days: int = 1,
    model_dir: Path = Path("models"),
) -> dict[str, tuple]:
    """Train all 4 models on the provided data.
    
    Args:
        features_df: DataFrame with engineered features
        targets_df: DataFrame with target labels
        horizon_days: Prediction horizon (1, 5, or 20)
        model_dir: Where to save trained models
        
    Returns:
        Dictionary mapping model_type -> (trainer, scaler)
    """
    logger.info(f"Generating training set for {horizon_days}-day prediction...")
    
    dataset_gen = DatasetGenerator()
    X, y = dataset_gen.get_training_set(
        features_df, targets_df,
        horizon_days=horizon_days,
        dropna=True,
    )
    
    logger.info(f"Training set shape: X={X.shape}, y={y.shape}")
    logger.info(f"Target distribution:\n{y.value_counts()}")
    
    # Split train/test (80/20)
    split_idx = int(0.8 * len(X))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    logger.info(f"Train/test split: {len(X_train)} / {len(X_test)}")
    
    # Train models
    model_server = ModelServer(model_dir=model_dir)
    trained_models = {}
    
    model_types = [
        ModelType.LOGISTIC_REGRESSION,
        ModelType.RANDOM_FOREST,
        ModelType.XGBOOST,
        ModelType.LIGHTGBM,
    ]
    
    for model_type in model_types:
        logger.info(f"Training {model_type}...")
        
        config = ModelConfig(model_type=model_type, scale_features=True)
        trainer = ModelTrainer(config)
        
        # Train
        trainer.train(X_train, y_train)
        
        # Evaluate
        evaluation = trainer.evaluate(X_test, y_test)
        
        logger.info(
            f"  Accuracy: {evaluation.accuracy:.4f}, "
            f"F1: {evaluation.f1:.4f}, "
            f"Precision: {evaluation.precision:.4f}, "
            f"Recall: {evaluation.recall:.4f}"
        )
        
        # Save model
        model_id = f"stock_prediction_{model_type}"
        version = f"v1_h{horizon_days}d"
        
        metadata = ModelMetadata(
            model_id=model_id,
            model_type=model_type,
            version=version,
            status=ModelStatus.READY,
            created_at=datetime.now(timezone.utc),
            accuracy=float(evaluation.accuracy),
            f1_score=float(evaluation.f1),
            roc_auc=float(evaluation.roc_auc) if evaluation.roc_auc else None,
            feature_names=list(X_train.columns),
            feature_count=X_train.shape[1],
            classes=list(trainer.model.classes_) if hasattr(trainer.model, 'classes_') else ["Negative", "Neutral", "Positive"],
            hyperparameters=config.__dict__,
            training_data_size=len(X_train),
            description=f"{model_type} for {horizon_days}-day stock price prediction",
        )
        
        scaler = trainer.scaler if hasattr(trainer, 'scaler') else None
        model_server.save_model(trainer.model, metadata, scaler)
        
        trained_models[model_type] = (trainer, scaler)
    
    logger.info("All models trained and saved")
    
    return trained_models


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Train ML models for stock price prediction")
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Specific symbol to train on (default: all)",
    )
    parser.add_argument(
        "--min-date",
        type=str,
        default="2023-01-01",
        help="Minimum date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--max-date",
        type=str,
        default=None,
        help="Maximum date (YYYY-MM-DD, default: today)",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=1,
        choices=[1, 5, 20],
        help="Prediction horizon in days",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="models",
        help="Directory to save models",
    )
    
    args = parser.parse_args()
    
    setup_logging()
    
    logger.info("=" * 60)
    logger.info("ML Model Training Pipeline")
    logger.info("=" * 60)
    
    # Parse dates
    min_date = datetime.strptime(args.min_date, "%Y-%m-%d").date()
    max_date = None
    if args.max_date:
        max_date = datetime.strptime(args.max_date, "%Y-%m-%d").date()
    
    logger.info(f"Symbol: {args.symbol or 'All'}")
    logger.info(f"Date range: {min_date} to {max_date or 'Today'}")
    logger.info(f"Horizon: {args.horizon} days")
    
    # Load data
    logger.info("\n1. Loading market data...")
    ohlcv_dict = load_ohlcv_from_db(
        symbol=args.symbol,
        min_date=min_date,
        max_date=max_date,
    )
    
    if not ohlcv_dict:
        logger.error("No data loaded")
        return 1
    
    # Generate features and targets per-symbol, then combine
    logger.info("\n2. Generating features and targets...")
    features_df, targets_df = process_data_by_symbol(ohlcv_dict)
    logger.info(f"Generated {features_df.shape[1]} features")
    logger.info(f"Generated targets for {len(targets_df)} trading days")
    
    # Train models
    logger.info(f"\n3. Training models (horizon={args.horizon} days)...")
    train_models_on_data(
        features_df=features_df,
        targets_df=targets_df,
        horizon_days=args.horizon,
        model_dir=Path(args.model_dir),
    )
    
    logger.info("\n" + "=" * 60)
    logger.info("Training complete!")
    logger.info("=" * 60)
    
    return 0


if __name__ == "__main__":
    exit(main())
