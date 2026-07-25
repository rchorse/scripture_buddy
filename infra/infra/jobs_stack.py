from aws_cdk import (
    Stack,
    aws_events as events,
    aws_events_targets as targets,
    Duration,
)
from constructs import Construct

from infra.api_stack import ApiStack


class JobsStack(Stack):
    """EventBridge schedules that invoke the API Lambda with task payloads.

    Job handlers live in api/app/jobs/ and are dispatched by main.handler.
    Schedules are created as milestones land; M0 ships the streak rollover
    placeholder disabled=False is fine because unknown tasks are no-ops.
    """

    def __init__(self, scope: Construct, construct_id: str, api: ApiStack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        def task_rule(rule_id: str, schedule: events.Schedule, task: str) -> None:
            rule = events.Rule(self, rule_id, schedule=schedule)
            rule.add_target(
                targets.LambdaFunction(
                    api.api_function,
                    event=events.RuleTargetInput.from_object({"task": task}),
                )
            )

        # Hourly: process users whose local midnight just passed (M4).
        task_rule("StreakRollover", events.Schedule.rate(Duration.hours(1)), "streak_rollover")
        # Hourly: streak reminders in each user's local evening window (M4).
        task_rule("Reminders", events.Schedule.rate(Duration.hours(1)), "reminders")
        # Weekly league finalize/reform — Monday 00:05 UTC (M6).
        task_rule(
            "LeagueReset",
            events.Schedule.cron(minute="5", hour="0", week_day="MON"),
            "league_reset",
        )
        # Daily: purge accounts past their deletion window (M5).
        task_rule(
            "RetentionSweep",
            events.Schedule.cron(minute="30", hour="9"),
            "retention_sweep",
        )
