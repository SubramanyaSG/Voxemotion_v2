"""
utils/dataset.py
================
ESD dataset scanner.
Returns empty DataFrame gracefully when dataset is absent
(Azure App Service — inference-only mode).
"""

import os
import pandas as pd

try:
    from config import DATASET_ROOT, SAMPLE_RATE
except ImportError:
    DATASET_ROOT = ''
    SAMPLE_RATE  = 22050

EMOTION_MAP = {
    'Angry':    'angry',
    'Happy':    'happy',
    'Neutral':  'neutral',
    'Sad':      'sad',
    'Surprise': 'surprise',
}


def get_dataset_df() -> pd.DataFrame:
    """
    Scan the ESD dataset and return a DataFrame with columns:
        path, emotion, speaker, text

    Returns an empty DataFrame (no crash) when DATASET_ROOT is
    missing or empty — which is the normal case on Azure.
    """
    if not DATASET_ROOT or not os.path.isdir(DATASET_ROOT):
        print(
            f'[dataset] DATASET_ROOT not found: "{DATASET_ROOT}" '
            '— running in inference-only mode.'
        )
        return pd.DataFrame(columns=['path', 'emotion', 'speaker', 'text'])

    records = []
    for speaker in sorted(os.listdir(DATASET_ROOT)):
        speaker_dir = os.path.join(DATASET_ROOT, speaker)
        if not os.path.isdir(speaker_dir):
            continue
        for emotion_raw, emotion_key in EMOTION_MAP.items():
            emo_dir = os.path.join(speaker_dir, emotion_raw)
            if not os.path.isdir(emo_dir):
                continue
            for fname in sorted(os.listdir(emo_dir)):
                if fname.lower().endswith('.wav'):
                    records.append({
                        'path':    os.path.join(emo_dir, fname),
                        'emotion': emotion_key,
                        'speaker': speaker,
                        'text':    os.path.splitext(fname)[0],
                    })

    df = pd.DataFrame(records)
    if df.empty:
        print('[dataset] No audio files found — inference-only mode.')
    else:
        print(f'[dataset] Loaded {len(df)} samples, '
              f'{df["emotion"].nunique()} emotions, '
              f'{df["speaker"].nunique()} speakers.')
    return df
