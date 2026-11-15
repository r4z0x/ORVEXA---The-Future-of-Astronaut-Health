"""Local SQLite storage. API credentials are never persisted."""
import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from .domain import Analysis, validate_ai_analysis

def timestamp():
    return datetime.now(timezone.utc).isoformat()

def default_data_dir():
    override = os.environ.get('ORVEXA_DATA_DIR')
    if override:
        return Path(override)
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'ORVEXA'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'orvexa'

class Repository:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else default_data_dir()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'orvexa.sqlite3'
        self.db = sqlite3.connect(self.path, timeout=3)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS measurements(id INTEGER PRIMARY KEY, at TEXT NOT NULL, data TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS analyses(id INTEGER PRIMARY KEY, measurement_id INTEGER, at TEXT NOT NULL, data TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY, at TEXT NOT NULL, seconds INTEGER NOT NULL, completed INTEGER NOT NULL, plan TEXT NOT NULL, mode TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS measurements_at ON measurements(at);
          CREATE INDEX IF NOT EXISTS analyses_measurement ON analyses(measurement_id,id);
        ''')
        # Upgrade 1.0 databases without deleting records or rewriting measurements.
        columns = {row['name'] for row in self.db.execute('PRAGMA table_info(analyses)')}
        if 'metrics' not in columns:
            self.db.execute('ALTER TABLE analyses ADD COLUMN metrics TEXT')
            self.db.execute('''UPDATE analyses SET metrics=(
                SELECT data FROM measurements WHERE measurements.id=analyses.measurement_id
            ) WHERE measurement_id IS NOT NULL''')
        self.db.commit()

    def add_measurement(self, metrics):
        metrics.validate()
        with self.db:
            row = self.db.execute('INSERT INTO measurements(at,data) VALUES(?,?)', (timestamp(), json.dumps(metrics.to_dict())))
            self.db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',
                            ('baseline', json.dumps(metrics.baseline_heart)))
        return row.lastrowid

    def measurements(self, limit=None, offset=0):
        if limit is not None and (not isinstance(limit, int) or limit < 1):
            raise ValueError('Page size must be positive.')
        rows = (self.db.execute('SELECT * FROM measurements ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset)) if limit is not None
                else self.db.execute('SELECT * FROM measurements ORDER BY id DESC')).fetchall()
        return [{'id': r['id'], 'at': r['at'], 'metrics': json.loads(r['data'])} for r in reversed(rows)]

    def measurement_range(self, since, until):
        rows = self.db.execute('SELECT * FROM measurements WHERE at>=? AND at<=? ORDER BY at,id',
                               (since.isoformat(), until.isoformat()))
        return [{'id': r['id'], 'at': r['at'], 'metrics': json.loads(r['data'])} for r in rows]

    def counts(self):
        measurements = self.db.execute('SELECT COUNT(*) FROM measurements').fetchone()[0]
        sessions = self.db.execute('SELECT COUNT(*),COALESCE(SUM(seconds),0) FROM sessions').fetchone()
        return measurements, sessions[0], sessions[1]

    def save_analysis(self, measurement_id, analysis, metrics=None):
        if metrics is None and measurement_id is not None:
            row = self.db.execute('SELECT data FROM measurements WHERE id=?', (measurement_id,)).fetchone()
            context = row['data'] if row else None
        else:
            context = json.dumps(metrics.to_dict()) if metrics is not None else None
        with self.db:
            self.db.execute('INSERT INTO analyses(measurement_id,at,data,metrics) VALUES(?,?,?,?)',
                            (measurement_id, timestamp(), json.dumps(analysis.to_dict(), ensure_ascii=False), context))

    def latest_analysis(self, measurement_id, metrics=None):
        row = self.db.execute('SELECT data,metrics FROM analyses WHERE measurement_id IS ? ORDER BY id DESC LIMIT 1', (measurement_id,)).fetchone()
        if not row:
            return None
        try:
            if metrics is not None and (not row['metrics'] or json.loads(row['metrics']) != metrics.to_dict()):
                return None
            data = json.loads(row['data'])
            if data.get('mode') == 'ai':
                return validate_ai_analysis(data, model=data.get('model', ''))
            return Analysis.from_dict(data)
        except (ValueError, TypeError, KeyError):
            # A bad cached response must not prevent opening the application.
            return None

    def add_session(self, seconds, completed, plan, mode):
        with self.db:
            self.db.execute('INSERT INTO sessions(at,seconds,completed,plan,mode) VALUES(?,?,?,?,?)',
                            (timestamp(), int(seconds), int(completed), json.dumps([e.to_dict() for e in plan], ensure_ascii=False), mode))

    def sessions(self, limit=None):
        query = 'SELECT * FROM sessions ORDER BY id DESC'
        rows = self.db.execute(query + ' LIMIT ?', (limit,)) if limit is not None else self.db.execute(query)
        return [dict(row) for row in rows]

    def get_setting(self, key, default=None):
        row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        try:
            return json.loads(row['value']) if row else default
        except (ValueError, TypeError):
            return default

    def set_setting(self, key, value):
        self.set_settings({key: value})

    def set_settings(self, values):
        if any(any(word in key.lower() for word in ('secret', 'token', 'key', 'password')) for key in values):
            raise ValueError('Persisting secrets is not allowed.')
        with self.db:
            self.db.executemany('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',
                                [(key, json.dumps(value, ensure_ascii=False)) for key, value in values.items()])

    def export(self):
        return {'app': 'ORVEXA', 'exported_at': timestamp(), 'measurements': self.measurements(),
                'sessions': [{**s, 'plan': json.loads(s['plan'])} for s in self.sessions()],
                'analyses': [{'at': r['at'], 'measurement_id': r['measurement_id'], 'analysis': json.loads(r['data']),
                              'metrics': json.loads(r['metrics']) if r['metrics'] else None}
                             for r in self.db.execute('SELECT * FROM analyses ORDER BY id')]}

    def close(self):
        self.db.close()
