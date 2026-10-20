import json
from typing import Any


class PromptBuilder:
    """Creates personalized, safety-aware prompts for the FitNova AI Coach."""

    PROFILE_FIELDS = [
        # Personal and physical profile
        "fullName", "age", "gender", "height", "weight", "medical",
        "state", "nativeState",

        # Fitness goals
        "goal", "targetWeight", "muscleGainTarget", "strengthGoal",
        "primaryLift", "repRange", "enduranceGoal", "cardioPreference",
        "fitnessGoals", "workoutPlace", "sportName", "performanceGoals",
        "competitionLevel", "workoutDays", "durationMonths", "activityLevel",
        "fitnessLevel",

        # Diet
        "dietaryPreferences", "allergies", "comments", "mealsPerDay",
        "budget",

        # Schedule, activity and recovery
        "sleepHours", "waterIntake", "job", "workoutTime", "breakTime",
        "officeTime", "exercise", "wakeUp", "workoutPrefer",
        "equipmentPrefer", "split", "customSplit",

        # Skin, hair and body
        "skinTone", "skinConcerns", "hairType", "hairConcerns",
        "bodyType", "bodyGoal", "scalpType",
    ]

    # Common database snake_case aliases are normalized to the onboarding
    # names used by the Flutter app.
    FIELD_ALIASES = {
        "full_name": "fullName",
        "target_weight": "targetWeight",
        "muscle_gain_target": "muscleGainTarget",
        "strength_goal": "strengthGoal",
        "primary_lift": "primaryLift",
        "rep_range": "repRange",
        "endurance_goal": "enduranceGoal",
        "cardio_preference": "cardioPreference",
        "fitness_goals": "fitnessGoals",
        "workout_place": "workoutPlace",
        "sport_name": "sportName",
        "performance_goals": "performanceGoals",
        "competition_level": "competitionLevel",
        "workout_days": "workoutDays",
        "duration_months": "durationMonths",
        "activity_level": "activityLevel",
        "fitness_level": "fitnessLevel",
        "dietary_preferences": "dietaryPreferences",
        "meals_per_day": "mealsPerDay",
        "sleep_hours": "sleepHours",
        "water_intake": "waterIntake",
        "workout_time": "workoutTime",
        "break_time": "breakTime",
        "office_time": "officeTime",
        "workout_prefer": "workoutPrefer",
        "equipment_prefer": "equipmentPrefer",
        "custom_split": "customSplit",
        "skin_tone": "skinTone",
        "skin_concerns": "skinConcerns",
        "hair_type": "hairType",
        "hair_concerns": "hairConcerns",
        "body_type": "bodyType",
        "body_goal": "bodyGoal",
        "scalp_type": "scalpType",
        "native_state": "nativeState",
    }

    @staticmethod
    def _json(value: Any) -> str:
        try:
            return json.dumps(
                value, ensure_ascii=False, indent=2, default=str
            )
        except (TypeError, ValueError):
            return str(value)

    def _prepare_profile(self, profile: Any) -> dict:
        if not isinstance(profile, dict):
            if hasattr(profile, "model_dump"):
                profile = profile.model_dump()
            elif hasattr(profile, "__dict__"):
                profile = vars(profile)
            else:
                return {}

        normalized = dict(profile)
        for source, target in self.FIELD_ALIASES.items():
            if source in profile and target not in normalized:
                normalized[target] = profile[source]
