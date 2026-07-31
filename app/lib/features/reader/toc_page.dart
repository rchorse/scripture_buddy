import 'package:flutter/material.dart';

import 'library_api.dart';
import 'library_models.dart';
import 'reader_page.dart';

/// Table of contents: books as expandable tiles, chapters as chips.
class TocPage extends StatefulWidget {
  const TocPage({super.key, required this.workSlug, required this.workTitle});

  final String workSlug;
  final String workTitle;

  @override
  State<TocPage> createState() => _TocPageState();
}

class _TocPageState extends State<TocPage> {
  final _api = LibraryApi();
  late Future<List<BookToc>> _toc;

  @override
  void initState() {
    super.initState();
    _toc = _api.tableOfContents(widget.workSlug);
  }

  Future<void> _resume() async {
    final divisionId = await _api.readingPosition(widget.workSlug);
    if (divisionId == null || !mounted) return;
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ReaderPage(
          workSlug: widget.workSlug,
          divisionId: divisionId,
          title: 'Continue reading',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.workTitle)),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _resume,
        icon: const Icon(Icons.bookmark),
        label: const Text('Resume'),
      ),
      body: FutureBuilder<List<BookToc>>(
        future: _toc,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return Center(child: Text('Error: ${snapshot.error}'));
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final books = snapshot.data!;
          return ListView.builder(
            itemCount: books.length,
            itemBuilder: (context, i) {
              final book = books[i];
              return ExpansionTile(
                title: Text(book.title),
                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    child: Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (final chapter in book.chapters)
                          ActionChip(
                            label: Text('${chapter.position}'),
                            onPressed: () => Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => ReaderPage(
                                  workSlug: widget.workSlug,
                                  divisionId: chapter.id,
                                  title: chapter.title,
                                ),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              );
            },
          );
        },
      ),
    );
  }
}
