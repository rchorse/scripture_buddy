/// Data classes for the lesson player. The server never sends the answer, so
/// there is deliberately no `answer` field here.
class LessonSummary {
  const LessonSummary({
    required this.id,
    required this.kind,
    required this.title,
    required this.exerciseCount,
  });

  final String id;
  final String kind;
  final String title;
  final int exerciseCount;

  factory LessonSummary.fromJson(Map<String, dynamic> json) => LessonSummary(
        id: json['id'] as String,
        kind: json['kind'] as String,
        title: json['title'] as String,
        exerciseCount: json['exercise_count'] as int,
      );
}

class ExerciseView {
  const ExerciseView({
    required this.id,
    required this.kind,
    required this.options,
    this.question,
    this.verseRef,
    this.displayText,
    this.lessonTitle,
  });

  final String id;
  final String kind;
  final List<String> options;
  final String? question;
  final String? verseRef;
  final String? displayText;
  final String? lessonTitle;

  /// What the learner reads above the answer choices.
  String get prompt => kind == 'mcq' ? (question ?? '') : (displayText ?? '');

  factory ExerciseView.fromJson(Map<String, dynamic> json) => ExerciseView(
        id: json['id'] as String? ?? json['exercise_id'] as String,
        kind: json['kind'] as String,
        options: (json['options'] as List).cast<String>(),
        question: json['question'] as String?,
        verseRef: json['verse_ref'] as String?,
        displayText: json['display_text'] as String?,
        lessonTitle: json['lesson_title'] as String?,
      );
}

class EarnedBadge {
  const EarnedBadge({required this.slug, required this.title, required this.description});

  final String slug;
  final String title;
  final String description;

  factory EarnedBadge.fromJson(Map<String, dynamic> json) => EarnedBadge(
        slug: json['slug'] as String,
        title: json['title'] as String,
        description: json['description'] as String? ?? '',
      );
}

class Rewards {
  const Rewards({
    required this.xpAwarded,
    required this.totalXp,
    required this.level,
    required this.leveledUp,
    required this.streak,
    required this.streakExtended,
    required this.newBadges,
  });

  final int xpAwarded;
  final int totalXp;
  final int level;
  final bool leveledUp;
  final int streak;
  final bool streakExtended;
  final List<EarnedBadge> newBadges;

  static const empty = Rewards(
    xpAwarded: 0,
    totalXp: 0,
    level: 1,
    leveledUp: false,
    streak: 0,
    streakExtended: false,
    newBadges: [],
  );

  factory Rewards.fromJson(Map<String, dynamic> json) => Rewards(
        xpAwarded: json['xp_awarded'] as int? ?? 0,
        totalXp: json['total_xp'] as int? ?? 0,
        level: json['level'] as int? ?? 1,
        leveledUp: json['leveled_up'] as bool? ?? false,
        streak: json['streak'] as int? ?? 0,
        streakExtended: json['streak_extended'] as bool? ?? false,
        newBadges: ((json['new_badges'] as List?) ?? [])
            .map((b) => EarnedBadge.fromJson(b as Map<String, dynamic>))
            .toList(),
      );
}

class AnswerResult {
  const AnswerResult({
    required this.correct,
    required this.correctAnswer,
    required this.explanation,
    required this.dueAt,
    this.rewards = Rewards.empty,
  });

  final bool correct;
  final String correctAnswer;
  final String explanation;
  final DateTime dueAt;
  final Rewards rewards;

  factory AnswerResult.fromJson(Map<String, dynamic> json) => AnswerResult(
        correct: json['correct'] as bool,
        correctAnswer: json['correct_answer'] as String,
        explanation: json['explanation'] as String? ?? '',
        dueAt: DateTime.parse(json['due_at'] as String),
        rewards: json['rewards'] == null
            ? Rewards.empty
            : Rewards.fromJson(json['rewards'] as Map<String, dynamic>),
      );

  /// Human-readable "you'll see this again in …" text.
  ///
  /// Rounds rather than truncates: a card scheduled 3.0 days out is "3 days",
  /// not the "2 days" that `inDays` would report a moment after scheduling.
  String get nextReviewLabel {
    final minutes =
        (dueAt.difference(DateTime.now().toUtc()).inSeconds / 60).round();
    if (minutes < 60) return 'Back in $minutes min';
    if (minutes < 48 * 60) {
      final hours = (minutes / 60).round();
      return 'Back in $hours hour${hours == 1 ? '' : 's'}';
    }
    final days = (minutes / (60 * 24)).round();
    return 'Back in $days days';
  }
}
