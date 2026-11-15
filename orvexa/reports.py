"""Atomic report writes: errors leave an existing report intact."""
import csv
import json
import os
from pathlib import Path
import tempfile

def save_report(path, report, format_name='json'):
    path = Path(path)
    if format_name not in ('json', 'csv'):
        raise ValueError('Unknown report format.')
    encoding = 'utf-8-sig' if format_name == 'csv' else 'utf-8'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding=encoding, newline='', dir=path.parent,
                                         prefix='.'+path.name+'.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            if format_name == 'json':
                json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            else:
                writer = csv.writer(stream, delimiter=';')
                writer.writerow(['Date','Heart Rate (bpm)','SpO2, %','Temperature, C','Sleep, h','Fatigue','Heart Rate Baseline','Discomfort'])
                for entry in report['measurements']:
                    m = entry['metrics']
                    writer.writerow([entry['at'], m['heart'], m['spo2'], m['temperature'], m['sleep_hours'],
                                     m['fatigue'], m['baseline_heart'], m['symptoms']])
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
