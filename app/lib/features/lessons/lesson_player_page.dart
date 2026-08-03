import 'package:flutter/material.dart';

import 'flag_sheet.dart';
import 'lesson_models.dart';
import 'lessons_api.dart';

/// Plays a sequence of exercises: prompt → choose → feedback → next → results.
/// Used for both chapter lessons and the daily review queue.
class LessonPlayerPage extends StatefulWidget {
  const LessonPlayerPage({
    super.key,
    required this.title,
    required this.load,
  });

  final String title;
  final Future<List<ExerciseView>> Function() load;

  @override
  State<LessonPlayerPage> createState() => _LessonPlayerPageState();
}

class _LessonPlayerPageState extends State<LessonPlayerPage> {
  final _api = LessonsApi();
  late Future<List<ExerciseView>> _exercises;
  List<ExerciseView> _items = const [];
  int _index = 0;
  int _correct = 0;
  int _xpEarned = 0;
  Rewards? _latestRewards;
  final List<EarnedBadge> _badgesEarned = [];
  String? _selected;
  AnswerResult? _result;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _exercises = widget.load()..then((items) => _items = items);
  }

  Future<void> _submit(String choice) async {
    if (_result != null || _submitting) return;
    setState(() {
      _selected = choice;
      _submitting = true;
    });
    try {
      final result = await _api.answer(_items[_index].id, choice);
      setState(() {
        _result = result;
        if (result.correct) _correct++;
        _xpEarned += result.rewards.xpAwarded;
        _latestRewards = result.rewards;
        _badgesEarned.addAll(result.rewards.newBadges);
      });
    } catch (e) {
      setState(() => _selected = null);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Could not submit: $e')));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _next() {
    setState(() {
      _index++;
      _selected = null;
      _result = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          if (_items.isNotEmpty && _index < _items.length)
            IconButton(
              tooltip: 'Report a problem with this question',
              icon: const Icon(Icons.flag_outlined),
              onPressed: () => showFlagSheet(context, _api, _items[_index].id),
            ),
        ],
        bottom: _items.isEmpty
            ? null
            : PreferredSize(
                preferredSize: const Size.fromHeight(4),
                child: LinearProgressIndicator(
                  value: _index / _items.length,
                  minHeight: 4,
                ),
              ),
      ),
      body: FutureBuilder<List<ExerciseView>>(
        future: _exercises,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return Center(child: Text('Error: ${snapshot.error}'));
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          _items = snapshot.data!;
          if (_items.isEmpty) {
            return const _EmptyState();
          }
          if (_index >= _items.length) {
            return _Results(
              correct: _correct,
              total: _items.length,
              xpEarned: _xpEarned,
              rewards: _latestRewards,
              badges: _badgesEarned,
            );
          }
          return _Question(
            exercise: _items[_index],
            selected: _selected,
            result: _result,
            onChoose: _submit,
            onNext: _next,
            isLast: _index == _items.length - 1,
          );
        },
      ),
    );
  }
}

class _Question extends StatelessWidget {
  const _Question({
    required this.exercise,
    required this.selected,
    required this.result,
    required this.onChoose,
    required this.onNext,
    required this.isLast,
  });

  final ExerciseView exercise;
  final String? selected;
  final AnswerResult? result;
  final void Function(String) onChoose;
  final VoidCallback onNext;
  final bool isLast;

  Color? _tileColor(BuildContext context, String option) {
    if (result == null) {
      return selected == option
          ? Theme.of(context).colorScheme.primaryContainer
          : null;
    }
    if (option == result!.correctAnswer) return const Color(0xFFC8E6C9);
    if (option == selected) return const Color(0xFFFFCDD2);
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        if (exercise.verseRef != null && exercise.verseRef!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              exercise.verseRef!,
              style: theme.textTheme.labelLarge
                  ?.copyWith(color: theme.colorScheme.primary),
            ),
          ),
        Text(
          exercise.prompt,
          style: theme.textTheme.titleMedium?.copyWith(height: 1.5),
        ),
        const SizedBox(height: 24),
        for (final option in exercise.options)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Material(
              color: _tileColor(context, option) ?? theme.colorScheme.surface,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(color: theme.dividerColor),
              ),
              child: InkWell(
                borderRadius: BorderRadius.circular(12),
                onTap: result == null ? () => onChoose(option) : null,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  child: Text(option, style: theme.textTheme.bodyLarge),
                ),
              ),
            ),
          ),
        if (result != null) ...[
          const SizedBox(height: 8),
          Card(
            color: result!.correct ? const Color(0xFFE8F5E9) : const Color(0xFFFFEBEE),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        result!.correct ? Icons.check_circle : Icons.cancel,
                        color: result!.correct
                            ? const Color(0xFF2E7D32)
                            : const Color(0xFFB3261E),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        result!.correct ? 'Correct' : 'Not quite',
                        style: theme.textTheme.titleMedium,
                      ),
                    ],
                  ),
                  if (result!.explanation.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(result!.explanation),
                  ],
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Text(
                        result!.nextReviewLabel,
                        style: theme.textTheme.bodySmall
                            ?.copyWith(color: theme.hintColor),
                      ),
                      const Spacer(),
                      if (result!.rewards.xpAwarded > 0)
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: const Color(0xFF2E7D32),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            '+${result!.rewards.xpAwarded} XP',
                            style: theme.textTheme.labelMedium
                                ?.copyWith(color: Colors.white),
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: onNext,
            child: Text(isLast ? 'See results' : 'Continue'),
          ),
        ],
      ],
    );
  }
}

class _Results extends StatelessWidget {
  const _Results({
    required this.correct,
    required this.total,
    required this.xpEarned,
    required this.rewards,
    required this.badges,
  });

  final int correct;
  final int total;
  final int xpEarned;
  final Rewards? rewards;
  final List<EarnedBadge> badges;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final pct = total == 0 ? 0 : (correct * 100 / total).round();
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 24),
        Icon(
          pct >= 80 ? Icons.emoji_events : Icons.school,
          size: 72,
          color: theme.colorScheme.primary,
        ),
        const SizedBox(height: 16),
        Text(
          '$correct of $total correct',
          textAlign: TextAlign.center,
          style: theme.textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        Text(
          pct >= 80
              ? 'Well done — these verses are sticking.'
              : 'Good effort. The ones you missed will come back sooner.',
          textAlign: TextAlign.center,
          style: theme.textTheme.bodyMedium,
        ),
        const SizedBox(height: 24),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _Stat(icon: Icons.bolt, label: '+$xpEarned XP'),
            if (rewards != null && rewards!.streak > 0) ...[
              const SizedBox(width: 12),
              _Stat(
                icon: Icons.local_fire_department,
                label: '${rewards!.streak} day'
                    '${rewards!.streak == 1 ? '' : 's'}',
              ),
            ],
          ],
        ),
        if (rewards?.leveledUp ?? false) ...[
          const SizedBox(height: 20),
          Card(
            color: const Color(0xFFFFF3CD),
            child: ListTile(
              leading: const Icon(Icons.arrow_circle_up, color: Color(0xFF8A6D00)),
              title: Text('Level ${rewards!.level}!'),
              subtitle: const Text('You reached a new level.'),
            ),
          ),
        ],
        for (final badge in badges) ...[
          const SizedBox(height: 12),
          Card(
            color: const Color(0xFFE8F5E9),
            child: ListTile(
              leading: const Icon(Icons.military_tech, color: Color(0xFF2E7D32)),
              title: Text('Badge earned: ${badge.title}'),
              subtitle: Text(badge.description),
            ),
          ),
        ],
        const SizedBox(height: 28),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Done'),
        ),
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 20, color: theme.colorScheme.primary),
          const SizedBox(width: 6),
          Text(label, style: theme.textTheme.titleSmall),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.check_circle_outline, size: 64, color: Colors.green),
            const SizedBox(height: 16),
            Text(
              'Nothing to review right now',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            const Text(
              'Come back when your next verses are due.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
