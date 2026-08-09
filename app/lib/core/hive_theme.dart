import 'package:flutter/material.dart';

/// The Hive palette and themes.
///
/// The metaphor is a beehive — honey, honeycomb, nectar — chosen because it
/// carries wisdom, sweetness and community without belonging to any one faith.
/// That matters: the content model holds any scripture, so the branding must
/// not pick a side by using sunrises, olive branches, scrolls or stars.
class HiveTheme {
  const HiveTheme._();

  /// Primary buttons, active states, progress fills.
  static const honeyGolden = Color(0xFFF5A623);

  /// Secondary accents, borders, streak badges.
  static const royalAmber = Color(0xFFE68A00);

  /// Scaffold background in light mode.
  static const parchmentCream = Color(0xFFFAF8F5);

  /// Body type in light mode; the background in dark.
  static const deepMidnight = Color(0xFF1E293B);

  /// Correct answers, completed lesson cells.
  static const sageGreen = Color(0xFF059669);

  /// Streak alerts and warnings.
  static const terracotta = Color(0xFFC2410C);

  /// Honey on parchment is a low-contrast pairing, so text sits on
  /// [deepMidnight] rather than on the amber itself wherever it can.
  static ThemeData get light => _build(Brightness.light);

  static ThemeData get dark => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final isDark = brightness == Brightness.dark;
    final scheme = ColorScheme(
      brightness: brightness,
      primary: honeyGolden,
      onPrimary: deepMidnight,
      secondary: royalAmber,
      onSecondary: Colors.white,
      tertiary: sageGreen,
      onTertiary: Colors.white,
      error: terracotta,
      onError: Colors.white,
      surface: isDark ? const Color(0xFF243044) : Colors.white,
      onSurface: isDark ? const Color(0xFFE8EDF5) : deepMidnight,
      surfaceContainerLowest: isDark ? deepMidnight : parchmentCream,
      outline: isDark ? const Color(0xFF3D4B63) : const Color(0xFFE0D8CC),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: isDark ? deepMidnight : parchmentCream,
      appBarTheme: AppBarTheme(
        backgroundColor: isDark ? deepMidnight : parchmentCream,
        foregroundColor: scheme.onSurface,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: scheme.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: scheme.outline),
        ),
        margin: const EdgeInsets.symmetric(vertical: 5),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: honeyGolden,
          // Amber is bright: dark type reads far better on it than white.
          foregroundColor: deepMidnight,
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 22),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(28),
          ),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: scheme.onSurface,
          side: BorderSide(color: royalAmber.withValues(alpha: 0.6)),
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 22),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(28),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: royalAmber),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: honeyGolden,
        linearMinHeight: 8,
      ),
      dividerTheme: DividerThemeData(color: scheme.outline, thickness: 1),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: deepMidnight,
        contentTextStyle: const TextStyle(color: Colors.white),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        focusedBorder: UnderlineInputBorder(
          borderSide: const BorderSide(color: royalAmber, width: 2),
          borderRadius: BorderRadius.circular(4),
        ),
      ),
    );
  }
}
