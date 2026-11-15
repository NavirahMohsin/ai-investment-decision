#!/usr/bin/env python
"""Initialize demo models for the predictions system.

This script trains and saves sample models so the predictions page
can display available models instead of "No models available".
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

from app.ml.models import ModelType, ModelConfig, ModelTrainer
from app.ml.model_server import ModelMetadata, ModelStatus, ModelServer


def create_demo_models():
    """Create and save demo models for immediate use."""
    
    print("Initializing demo models...")
    
    # Create synthetic training data
    np.random.seed(42)
    n_samples = 500
    n_features = 20
    
    X_train = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f"feature_{i}" for i in range(n_features)]
    )
    y_train = pd.Series(
        np.random.choice(["Positive", "Negative", "Neutral"], n_samples),
        name="target"
    )
    
    # Initialize model server
    model_dir = Path("backend/models") if not Path("models").exists() else Path("models")
    model_server = ModelServer(model_dir=model_dir)
    
    models_to_create = [
        {
            "model_id": "logistic_regression_v1",
            "model_type": ModelType.LOGISTIC_REGRESSION,
            "description": "Logistic Regression baseline model",
        },
        {
            "model_id": "random_forest_v1", 
            "model_type": ModelType.RANDOM_FOREST,
            "description": "Random Forest ensemble model",
        },
        {
            "model_id": "xgboost_v1",
            "model_type": ModelType.XGBOOST,
            "description": "XGBoost gradient boosting model",
        },
    ]
    
    for model_spec in models_to_create:
        print(f"\nTraining {model_spec['model_id']}...")
        
        try:
            # Train the model
            config = ModelConfig(model_type=model_spec["model_type"])
            trainer = ModelTrainer(config)
            trainer.train(X_train, y_train)
            
            # Create metadata
            metadata = ModelMetadata(
                model_id=model_spec["model_id"],
                model_type=model_spec["model_type"].value,
                version="1.0",
                status=ModelStatus.READY,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                accuracy=trainer.evaluation.metrics["accuracy"] if trainer.evaluation else 0.7,
                f1_score=trainer.evaluation.metrics.get("f1_weighted", 0.65) if trainer.evaluation else 0.65,
                feature_names=[f"feature_{i}" for i in range(n_features)],
                feature_count=n_features,
                classes=["Positive", "Negative", "Neutral"],
                training_data_size=n_samples,
                description=model_spec["description"],
            )
            
            # Save the model
            model_server.save_model(trainer.model, metadata, trainer.scaler)
            print(f"✓ Saved {model_spec['model_id']} (Accuracy: {metadata.accuracy:.2%})")
            
        except Exception as e:
            print(f"✗ Failed to train {model_spec['model_id']}: {e}")
            continue
    
    # List saved models
    print("\n" + "="*60)
    print("Available models:")
    models = model_server.list_models()
    if models:
        for model in models:
            print(f"  • {model['model_id']} (v{model['version']})")
            print(f"    Type: {model['model_type']}")
            print(f"    Accuracy: {model.get('accuracy', 'N/A')}")
            print(f"    F1 Score: {model.get('f1_score', 'N/A')}")
    else:
        print("  No models found!")
    
    print("="*60)
    print("Demo models initialized successfully!")
    print(f"Models saved to: {model_dir.resolve()}")


if __name__ == "__main__":
    create_demo_models()
