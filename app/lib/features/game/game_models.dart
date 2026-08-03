/// Progress shown on the home screen.
class StreakInfo {
  const StreakInfo({
    required this.current,
    required this.longest,
    required this.freezesAvailable,
    required this.practisedToday,
    required this.atRisk,
  });

  final int current;
  final int longest;
  final int freezesAvailable;
  final bool practisedToday;
  final bool atRisk;

  factory StreakInfo.fromJson(Map<String, dynamic> json) => StreakInfo(
        current: json['current'] as int? ?? 0,
        longest: json['longest'] as int? ?? 0,
        freezesAvailable: json['freezes_available'] as int? ?? 0,
        practisedToday: json['practised_today'] as bool? ?? false,
        atRisk: json['at_risk'] as bool? ?? false,
      );
}

class BadgeInfo {
  const BadgeInfo({
    required this.slug,
    required this.title,
    required this.description,
    required this.earned,
  });

  final String slug;
  final String title;
  final String description;
  final bool earned;

  factory BadgeInfo.fromJson(Map<String, dynamic> json) => BadgeInfo(
        slug: json['slug'] as String,
        title: json['title'] as String,
        description: json['description'] as String? ?? '',
        earned: json['earned'] as bool? ?? false,
      );
}

class GameProgress {
  const GameProgress({
    required this.level,
    required this.totalXp,
    required this.xpIntoLevel,
    required this.xpToNextLevel,
    required this.fraction,
    required this.streak,
    required this.badges,
  });

  final int level;
  final int totalXp;
  final int xpIntoLevel;
  final int xpToNextLevel;
  final double fraction;
  final StreakInfo streak;
  final List<BadgeInfo> badges;

  int get badgesEarned => badges.where((b) => b.earned).length;

  factory GameProgress.fromJson(Map<String, dynamic> json) => GameProgress(
        level: json['level'] as int? ?? 1,
        totalXp: json['total_xp'] as int? ?? 0,
        xpIntoLevel: json['xp_into_level'] as int? ?? 0,
        xpToNextLevel: json['xp_to_next_level'] as int? ?? 0,
        fraction: (json['fraction'] as num?)?.toDouble() ?? 0.0,
        streak: StreakInfo.fromJson(
          (json['streak'] as Map<String, dynamic>?) ?? const {},
        ),
        badges: ((json['badges'] as List?) ?? [])
            .map((b) => BadgeInfo.fromJson(b as Map<String, dynamic>))
            .toList(),
      );
}
