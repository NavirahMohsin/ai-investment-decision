"""Test the best model for predictions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.ml.model_server import ModelServer
from app.db.session import SessionLocal
from app.db.models import Company, DailyMarketData
import pandas as pd
import numpy as np
from sqlalchemy import select


def test_best_model():
    """Test loading and using the best model."""
    
    print("\n" + "="*80)
    print("Testing Best Model (XGBoost - 56.53% accuracy)")
    print("="*80)
    
    # Initialize model server
    model_server = ModelServer(model_dir=Path("models"))
    
    # Test 1: List available models
    print("\n[1] Listing available models...")
    models = model_server.list_models()
    print(f"Found {len(models)} models:")
    for m in models:
        print(f"  - {m['model_id']} ({m['model_type']}) v{m['version']}")
        if 'accuracy' in m and m['accuracy']:
            print(f"    Accuracy: {m['accuracy']:.2%}")
    
    # Test 2: Load best model
    print("\n[2] Loading best model...")
    try:
        model, metadata, scaler = model_server.load_model(
            "stock_prediction_xgboost_all",
            "latest"
        )
        print(f"[OK] Loaded: {metadata.model_id}")
        print(f"  Type: {metadata.model_type}")
        print(f"  Accuracy: {metadata.accuracy:.2%}")
        print(f"  F1-Score: {metadata.f1_score:.4f}")
        print(f"  Features: {metadata.feature_count}")
        print(f"  Classes: {metadata.classes}")
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        return 1
    
    # Test 3: Get latest market data
    print("\n[3] Fetching latest market data...")
    with SessionLocal() as db:
        # Get RELIANCE
        company = db.scalars(
            select(Company).where(Company.symbol == "RELIANCE")
        ).first()
        
        if not company:
            print("[ERROR] RELIANCE not found in database")
            return 1
        
        # Get last 500 trading days
        market_data = db.scalars(
            select(DailyMarketData)
            .where(DailyMarketData.company_id == company.id)
            .order_by(DailyMarketData.trading_date.desc())
            .limit(500)
        ).all()
        
        if not market_data:
            print("[ERROR] No market data for RELIANCE")
            return 1
        
        # Reverse to chronological order
        market_data = list(reversed(market_data))
        print(f"[OK] Loaded {len(market_data)} trading days")
        
        # Build DataFrame
        data = pd.DataFrame([
            {
                "trading_date": row.trading_date,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": row.volume,
            }
            for row in market_data
        ])
        
        latest_date = market_data[-1].trading_date
        latest_price = float(market_data[-1].close)
        print(f"  Latest: {latest_date} @ Rs{latest_price:.2f}")
    
    # Test 4: Generate features
    print("\n[4] Generating features...")
    from app.ml.feature_engineering import DatasetGenerator
    
    try:
        dataset_gen = DatasetGenerator()
        features_df = dataset_gen.generate_features(data)
        print(f"[OK] Generated {len(features_df)} rows x {len(features_df.columns)} features")
        
        # Get latest features
        latest_features = features_df.iloc[-1:].dropna()
        if latest_features.empty:
            print("[ERROR] No valid features for latest row")
            return 1
        
        print(f"[OK] Latest features ready: {latest_features.shape}")
    except Exception as e:
        print(f"[ERROR] Feature generation failed: {e}")
        return 1
    
    # Test 5: Make prediction
    print("\n[5] Making prediction...")
    try:
        # Get prediction - drop non-numeric columns
        feature_row = latest_features.drop(columns=['trading_date'], errors='ignore')
        feature_values = feature_row.values.astype(np.float32)
        
        # Get prediction
        result = model_server.predict(
            "stock_prediction_xgboost_all",
            "latest",
            feature_values
        )
        
        # Handle both single and batch results
        if isinstance(result, list):
            result = result[0]
        
        print(f"[OK] Prediction: {result.predicted_class}")
        print(f"  Confidence: {result.confidence:.1%}")
        print(f"  Probabilities:")
        for cls, prob in result.class_probabilities.items():
            print(f"    - {cls}: {prob:.2%}")
        print(f"  Prediction ID: {result.prediction_id}")
        
    except Exception as e:
        print(f"[ERROR] Prediction failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "="*80)
    print("SUCCESS! Model is ready for predictions.")
    print("="*80)
    
    return 0


if __name__ == "__main__":
    exit(test_best_model())
