#!/usr/bin/env python3
"""Quick test of FinBERT sentiment analysis."""

from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import logging

logging.basicConfig(level=logging.INFO)

print('Testing FinBERT model...')
model_name = 'ProsusAI/finbert'

try:
    print(f'Loading {model_name}...')
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    
    # Create pipeline
    sentiment_pipeline = pipeline(
        "sentiment-analysis",
        model=model,
        tokenizer=tokenizer,
        device=-1
    )
    
    # Test with sample financial texts
    test_texts = [
        "Earnings beat expectations and revenue surged",
        "Stock plunged after lawsuit filing",
        "Company acquires competitor for strategic growth",
        "Regulatory approval received, stock steady",
        "CEO resignation sparked investor concerns"
    ]
    
    print('\nTesting FinBERT sentiment analysis:')
    print('-' * 70)
    for text in test_texts:
        result = sentiment_pipeline(text)
        label = result[0]['label'].upper()
        score = result[0]['score']
        print(f"Text: {text}")
        print(f"  → {label} (confidence: {score:.3f})")
        print()
    
    print('✓ FinBERT working correctly!')
    print(f'Model: {model_name}')
    print(f'Parameters: {model.num_parameters():,}')
    
except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()
