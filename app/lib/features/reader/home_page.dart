import 'package:flutter/material.dart';

import '../game/game_models.dart';
import '../social/approvals_page.dart';
import '../social/friends_page.dart';
import '../social/league_page.dart';
import '../game/progress_header.dart';
import '../lessons/lesson_player_page.dart';
import '../lessons/lessons_api.dart';
import 'library_api.dart';
import 'library_models.dart';
import 'toc_page.dart';

/// Post-login home: the released works library.
class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final _api = LibraryApi();
  final _lessons = LessonsApi();
  late Future<List<WorkSummary>> _works;
  late Future<GameProgress> _progress;

  @override
  void initState() {
    super.initState();
    _works = _api.listWorks();
    _progress = _lessons.progress();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Library'),
        actions: [
          IconButton(
            tooltip: 'Leaderboards',
            icon: const Icon(Icons.leaderboard),
            onPressed: () async {
              await Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const LeaguePage()),
              );
              if (mounted) setState(() => _progress = _lessons.progress());
            },
          ),
          IconButton(
            tooltip: 'Friends',
            icon: const Icon(Icons.people_outline),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const FriendsPage()),
            ),
          ),
          IconButton(
            tooltip: 'Friend approvals',
            icon: const Icon(Icons.family_restroom),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const ApprovalsPage()),
            ),
          ),
        ],
      ),
      body: FutureBuilder<List<WorkSummary>>(
        future: _works,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return Center(child: Text('Error: ${snapshot.error}'));
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final works = snapshot.data!;
          if (works.isEmpty) {
            return const Center(child: Text('No books released yet.'));
          }
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              ProgressHeader(future: _progress),
              const SizedBox(height: 8),
              Card(
                color: Theme.of(context).colorScheme.primaryContainer,
                child: ListTile(
                  leading: const Icon(Icons.psychology),
                  title: const Text('Daily review'),
                  subtitle: const Text('Verses due for practice'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () async {
                    await Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => LessonPlayerPage(
                          title: 'Daily review',
                          load: () => _lessons.dueReviews(),
                        ),
                      ),
                    );
                    setState(() => _progress = _lessons.progress());
                  },
                ),
              ),
              const SizedBox(height: 8),
              for (final work in works)
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.menu_book),
                    title: Text(work.title),
                    onTap: () async {
                      await Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) =>
                              TocPage(workSlug: work.slug, workTitle: work.title),
                        ),
                      );
                      setState(() => _progress = _lessons.progress());
                    },
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
