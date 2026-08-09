/// The Hive vocabulary.
///
/// Gamification terms live here so the metaphor stays consistent wherever it
/// surfaces — screens, reward sheets, and later push notifications. Points are
/// **Nectar Drops** and the streak is a **Honey Jar**; "XP" and "streak" are
/// implementation words that should not reach a reader.
///
/// The app is still called ScriptureBuddy. The brand document proposed "Hive
/// Study", but the name is already the domain, the Cognito pool, the store
/// listing drafts and the published privacy policy — so the hive is the
/// metaphor, not the name.
class HiveStrings {
  const HiveStrings._();

  static const appName = 'ScriptureBuddy';

  /// "12 Nectar Drops", but "1 Nectar Drop".
  static String nectar(int amount) =>
      '$amount Nectar ${amount == 1 ? 'Drop' : 'Drops'}';

  static String nectarGained(int amount) => '+${nectar(amount)}';

  /// The jar fills as the streak grows, so a streak reads as days of honey.
  static String jarStatus(int days) => days == 1 ? '1 day of honey' : '$days days of honey';

  static const jarEmpty = 'Your honey jar is empty';

  static const jarAtRisk =
      'Your jar is running low — a few minutes today tops it up';

  static const lessonSuccess =
      'Unbee-lievable. Another drop of wisdom in your jar.';

  /// Unused until the FCM reminder job exists — kept so the copy is written
  /// once, in the same voice as everything else.
  static const streakReminder =
      'Desi is waiting at the hive. Keep your jar full with a 3-minute review.';

  static String toNextLevel(int drops, int level) =>
      '${nectar(drops)} to level $level';
}
