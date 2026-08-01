import 'package:flutter/material.dart';

import '../lessons/lesson_models.dart';
import '../lessons/lesson_player_page.dart';
import '../lessons/lessons_api.dart';
import 'library_api.dart';
import 'library_models.dart';

/// Chapter reader: verse list with position saved on scroll settle.
class ReaderPage extends StatefulWidget {
  const ReaderPage({
    super.key,
    required this.workSlug,
    required this.divisionId,
    required this.title,
  });

  final String workSlug;
  final String divisionId;
  final String title;

  @override
  State<ReaderPage> createState() => _ReaderPageState();
}

class _ReaderPageState extends State<ReaderPage> {
  final _api = LibraryApi();
  final _lessons = LessonsApi();
  late Future<List<VerseText>> _verses;
  late Future<List<LessonSummary>> _chapterLessons;

  @override
  void initState() {
    super.initState();
    _verses = _api.verses(widget.divisionId);
    _chapterLessons = _lessons.lessonsForChapter(widget.divisionId);
    // Opening a chapter is the position signal for M1; per-verse scroll
    // tracking arrives with the lessons UI in M3.
    _api.savePosition(widget.workSlug, widget.divisionId, 1).ignore();
  }

  void _showLessonPicker(List<LessonSummary> lessons) {
    showModalBottomSheet<void>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final lesson in lessons)
              ListTile(
                leading: Icon(
                  lesson.kind == 'memorize' ? Icons.psychology : Icons.quiz,
                ),
                title: Text(lesson.title),
                subtitle: Text('${lesson.exerciseCount} questions'),
                onTap: () {
                  Navigator.of(sheetContext).pop();
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => LessonPlayerPage(
                        title: lesson.title,
                        load: () => _lessons.exercises(lesson.id),
                      ),
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      floatingActionButton: FutureBuilder<List<LessonSummary>>(
        future: _chapterLessons,
        builder: (context, snapshot) {
          final lessons = snapshot.data ?? const <LessonSummary>[];
          if (lessons.isEmpty) return const SizedBox.shrink();
          return FloatingActionButton.extended(
            icon: const Icon(Icons.school),
            label: const Text('Practice'),
            onPressed: () => _showLessonPicker(lessons),
          );
        },
      ),
      body: FutureBuilder<List<VerseText>>(
        future: _verses,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return Center(child: Text('Error: ${snapshot.error}'));
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final verses = snapshot.data!;
          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: verses.length,
            itemBuilder: (context, i) {
              final verse = verses[i];
              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: RichText(
                  text: TextSpan(
                    style: textTheme.bodyLarge?.copyWith(height: 1.5),
                    children: [
                      TextSpan(
                        text: '${verse.position} ',
                        style: textTheme.labelSmall?.copyWith(
                          color: Theme.of(context).colorScheme.primary,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      TextSpan(text: verse.text),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
