"""Models, validation and conservative exercise guardrails; no GUI dependencies."""
from dataclasses import dataclass, asdict
import math

@dataclass(frozen=True)
class Metrics:
    heart: float = 68
    spo2: float = 98
    temperature: float = 36.6
    sleep_hours: float = 6.7
    fatigue: float = 3
    baseline_heart: float = 61
    symptoms: bool = False

    def validate(self):
        bounds = {
            'heart': (30, 220), 'spo2': (50, 100), 'temperature': (32, 43),
            'sleep_hours': (0, 16), 'fatigue': (0, 10), 'baseline_heart': (35, 110),
        }
        for key, (low, high) in bounds.items():
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f'Invalid metric value: {key}')
        if not isinstance(self.symptoms, bool):
            raise ValueError('The well-being field must be a boolean.')
        return self

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**{key: data[key] for key in cls.__dataclass_fields__}).validate()

    def concerns(self):
        result = []
        if self.heart < 45 or self.heart > 110:
            result.append('Unusual resting heart rate')
        if self.spo2 < 94:
            result.append('Low oxygen saturation')
        if self.temperature < 35 or self.temperature >= 38:
            result.append('Unusual temperature')
        if self.symptoms:
            result.append('Pain, dizziness, or discomfort reported')
        return result

@dataclass(frozen=True)
class Exercise:
    name: str
    equipment: str
    minutes: int
    description: str
    steps: str
    category: str = 'Fitness Support'

    def to_dict(self):
        return asdict(self)

@dataclass(frozen=True)
class Analysis:
    title: str
    summary: str
    reasons: tuple
    plan: tuple
    mode: str = 'ai'
    model: str = ''

    def to_dict(self):
        return {'title': self.title, 'summary': self.summary, 'reasons': list(self.reasons),
                'plan': [e.to_dict() for e in self.plan], 'mode': self.mode, 'model': self.model}

    @classmethod
    def from_dict(cls, data):
        return cls(data['title'], data['summary'], tuple(data['reasons']),
                   tuple(Exercise(**x) for x in data['plan']), data.get('mode', 'ai'), data.get('model', ''))

def safety_analysis(metrics):
    return Analysis('Medical Review Required First',
                    'The readings or reported well-being require attention. The automatic workout plan has been paused. Contact the mission medical officer.',
                    tuple(metrics.concerns()), (), mode='guardrail')

def sample_plan(metrics):
    if metrics.concerns():
        return ()
    reduced = metrics.sleep_hours < 7 or metrics.fatigue >= 6 or metrics.heart - metrics.baseline_heart > 10
    return (
        Exercise('Strength Support', 'ARED', 15 if reduced else 20,
                 'Support for muscle and bone health.',
                 'Use restraints. Move smoothly and do not hold your breath. Resistance and technique must be determined by the mission instructor.', 'Strength'),
        Exercise('Cycle Training', 'CEVIS', 10 if reduced else 15,
                 'Aerobic conditioning and endurance.',
                 'Secure yourself in the device. Begin with easy pedaling. Agree on intensity and duration with the mission medical officer.', 'Cardio'),
        Exercise('Mobility & Stretching', 'Restraints', 10,
                 'Joint mobility and recovery.',
                 'Use a secure support. Move your shoulders, wrists, and ankles smoothly within a comfortable range. Do not stretch through pain.', 'Recovery'),
    )

def sleep_label(hours):
    total = round(hours * 60)
    return f'{total // 60} h {total % 60:02d} min'

def validate_ai_analysis(data, model=''):
    if not isinstance(data, dict):
        raise ValueError('The model returned an invalid analysis format.')
    for name in ('title', 'summary'):
        if not isinstance(data.get(name), str) or not data[name].strip():
            raise ValueError('The model returned an incomplete analysis. Please try again.')
    raw_plan = data.get('plan')
    reasons = data.get('reasons')
    if not isinstance(raw_plan, list) or len(raw_plan) > 3 or not isinstance(reasons, list) or any(not isinstance(x, str) for x in reasons):
        raise ValueError('The model returned an invalid plan.')
    exercises = []
    for item in raw_plan:
        if not isinstance(item, dict):
            raise ValueError('Invalid exercise.')
        minutes = item.get('minutes')
        if isinstance(minutes, bool) or not isinstance(minutes, int) or not 3 <= minutes <= 30:
            raise ValueError('Exercise duration is outside the allowed range.')
        text = {}
        for key in ('name', 'equipment', 'description', 'steps'):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError('The model did not fully describe the exercise.')
            text[key] = item[key][:1500 if key == 'steps' else 300]
        category = item.get('category', 'Fitness Support')
        text['category'] = category[:80] if isinstance(category, str) else 'Fitness Support'
        exercises.append(Exercise(minutes=minutes, **text))
    if sum(e.minutes for e in exercises) > 60:
        raise ValueError('The model proposed a plan longer than 60 minutes. Please try again.')
    return Analysis(data['title'][:150], data['summary'][:2500], tuple(x[:150] for x in reasons[:4]), tuple(exercises), model=model)
