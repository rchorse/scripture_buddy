import 'package:flutter/material.dart';

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
  late Future<List<VerseText>> _verses;

  @override
  void initState() {
    super.initState();
    _verses = _api.verses(widget.divisionId);
    // Opening a chapter is the position signal for M1; per-verse scroll
    // tracking arrives with the lessons UI in M3.
    _api.savePosition(widget.workSlug, widget.divisionId, 1).ignore();
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
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
