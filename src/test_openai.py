#!/usr/bin/env python3
"""
Test script to verify OpenAI API key and embedding generation
"""
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print(f"Testing OpenAI API...")
print(f"API Key configured: {'Yes' if OPENAI_API_KEY else 'No'}")

if not OPENAI_API_KEY:
    print("[ERROR] OPENAI_API_KEY not found in environment")
    exit(1)

print(f"API Key (first 20 chars): {OPENAI_API_KEY[:20]}...")

try:
    client = OpenAI(api_key=OPENAI_API_KEY)
    print("[OK] OpenAI client initialized")

    # Test embedding generation
    print("\nGenerating test embedding...")
    test_text = "Esta es una prueba de generacion de embeddings para EGESUR."

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=test_text
    )

    embedding = response.data[0].embedding
    print(f"[OK] Embedding generado exitosamente")
    print(f"  - Dimensiones: {len(embedding)}")
    print(f"  - Primeros 5 valores: {embedding[:5]}")
    print(f"\n[SUCCESS] OpenAI API funciona correctamente!")

except Exception as e:
    print(f"\n[ERROR] {str(e)}")
    import traceback
    traceback.print_exc()
    exit(1)
