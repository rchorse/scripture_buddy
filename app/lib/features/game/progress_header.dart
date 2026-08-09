import 'package:flutter/material.dart';

import '../../core/hive_strings.dart';
import '../../core/hive_theme.dart';
import 'game_models.dart';

/// Streak, level and XP bar at the top of the library.
class ProgressHeader extends StatelessWidget {
  const ProgressHeader({super.key, required this.future});

  final Future<GameProgress> future;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return FutureBuilder<GameProgress>(
      future: future,
      builder: (context, snapshot) {
        if (!snapshot.hasData) return const SizedBox(height: 8);
        final p = snapshot.data!;
        return Card(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      Icons.emoji_food_beverage,
                      color: p.streak.current > 0
                          ? HiveTheme.royalAmber
                          : theme.disabledColor,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      p.streak.current > 0
                          ? HiveStrings.jarStatus(p.streak.current)
                          : HiveStrings.jarEmpty,
                      style: theme.textTheme.titleMedium,
                    ),
                    const Spacer(),
                    Icon(Icons.military_tech,
                        size: 20, color: theme.colorScheme.primary),
                    const SizedBox(width: 4),
                    Text('${p.badgesEarned}', style: theme.textTheme.titleSmall),
                  ],
                ),
                if (p.streak.atRisk)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      HiveStrings.jarAtRisk,
                      style: theme.textTheme.bodySmall
                          ?.copyWith(color: HiveTheme.terracotta),
                    ),
                  ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Text('Level ${p.level}', style: theme.textTheme.labelLarge),
                    const Spacer(),
                    Text(
                      HiveStrings.toNextLevel(p.xpToNextLevel, p.level + 1),
                      style: theme.textTheme.bodySmall
                          ?.copyWith(color: theme.hintColor),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                ClipRRect(
                  borderRadius: BorderRadius.circular(999),
                  child: LinearProgressIndicator(
                    value: p.fraction,
                    minHeight: 8,
                    backgroundColor: theme.colorScheme.surfaceContainerHighest,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
