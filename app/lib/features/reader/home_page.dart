import 'package:flutter/material.dart';

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
  late Future<List<WorkSummary>> _works;

  @override
  void initState() {
    super.initState();
    _works = _api.listWorks();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Library')),
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
              Card(
                color: Theme.of(context).colorScheme.primaryContainer,
                child: ListTile(
                  leading: const Icon(Icons.psychology),
                  title: const Text('Daily review'),
                  subtitle: const Text('Verses due for practice'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => LessonPlayerPage(
                        title: 'Daily review',
                        load: () => LessonsApi().dueReviews(),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              for (final work in works)
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.menu_book),
                    title: Text(work.title),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) =>
                            TocPage(workSlug: work.slug, workTitle: work.title),
                      ),
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
