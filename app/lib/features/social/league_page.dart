import 'package:flutter/material.dart';

import 'social_api.dart';
import 'social_models.dart';

/// Weekly league cohort, with the friends leaderboard as a second tab.
class LeaguePage extends StatefulWidget {
  const LeaguePage({super.key});

  @override
  State<LeaguePage> createState() => _LeaguePageState();
}

class _LeaguePageState extends State<LeaguePage> {
  final _api = SocialApi();
  late Future<Standings> _league;
  late Future<Standings> _friends;

  @override
  void initState() {
    super.initState();
    _league = _api.league();
    _friends = _api.leaderboard();
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Leaderboards'),
          bottom: const TabBar(
            tabs: [Tab(text: 'League'), Tab(text: 'Friends')],
          ),
        ),
        body: TabBarView(
          children: [
            _StandingsView(future: _league, showZones: true),
            _StandingsView(future: _friends, showZones: false),
          ],
        ),
      ),
    );
  }
}

class _StandingsView extends StatelessWidget {
  const _StandingsView({required this.future, required this.showZones});

  final Future<Standings> future;
  final bool showZones;

  Color? _zoneColor(String zone) => switch (zone) {
        'promote' => const Color(0xFFE8F5E9),
        'demote' => const Color(0xFFFFEBEE),
        _ => null,
      };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return FutureBuilder<Standings>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(child: Text('${snapshot.error}'));
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final standings = snapshot.data!;
        if (!standings.available) {
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.lock_outline, size: 56),
                  const SizedBox(height: 16),
                  Text(standings.reason, textAlign: TextAlign.center),
                ],
              ),
            ),
          );
        }
        if (standings.rows.isEmpty) {
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Text(
                standings.note.isNotEmpty
                    ? standings.note
                    : 'Nothing here yet — add a friend to compare progress.',
                textAlign: TextAlign.center,
              ),
            ),
          );
        }
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (standings.tier.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Row(
                  children: [
                    Icon(Icons.shield, color: theme.colorScheme.primary),
                    const SizedBox(width: 8),
                    Text('${standings.tier} league',
                        style: theme.textTheme.titleMedium),
                  ],
                ),
              ),
            if (showZones)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  'Top 7 move up, bottom 7 move down when the week ends.',
                  style:
                      theme.textTheme.bodySmall?.copyWith(color: theme.hintColor),
                ),
              ),
            for (final row in standings.rows)
              Card(
                color: showZones
                    ? _zoneColor(row.zone)
                    : (row.isYou ? theme.colorScheme.primaryContainer : null),
                child: ListTile(
                  leading: SizedBox(
                    width: 32,
                    child: Text(
                      '${row.rank}',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.titleMedium,
                    ),
                  ),
                  title: Text(
                    row.name,
                    style: row.isYou
                        ? const TextStyle(fontWeight: FontWeight.bold)
                        : null,
                  ),
                  subtitle: row.isYou ? const Text('You') : null,
                  trailing: Text('${row.xp} XP',
                      style: theme.textTheme.titleSmall),
                ),
              ),
          ],
        );
      },
    );
  }
}
