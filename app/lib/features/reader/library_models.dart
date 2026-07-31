/// Plain data classes for the library/reader feature.
class WorkSummary {
  const WorkSummary({required this.slug, required this.title});

  final String slug;
  final String title;

  factory WorkSummary.fromJson(Map<String, dynamic> json) =>
      WorkSummary(slug: json['slug'] as String, title: json['title'] as String);
}

class ChapterRef {
  const ChapterRef({required this.id, required this.position, required this.title});

  final String id;
  final int position;
  final String title;

  factory ChapterRef.fromJson(Map<String, dynamic> json) => ChapterRef(
        id: json['id'] as String,
        position: json['position'] as int,
        title: json['title'] as String,
      );
}

class BookToc {
  const BookToc({required this.title, required this.chapters});

  final String title;
  final List<ChapterRef> chapters;

  factory BookToc.fromJson(Map<String, dynamic> json) => BookToc(
        title: json['title'] as String,
        chapters: (json['chapters'] as List)
            .map((c) => ChapterRef.fromJson(c as Map<String, dynamic>))
            .toList(),
      );
}

class VerseText {
  const VerseText({required this.position, required this.ref, required this.text});

  final int position;
  final String ref;
  final String text;

  factory VerseText.fromJson(Map<String, dynamic> json) => VerseText(
        position: json['position'] as int,
        ref: json['ref'] as String,
        text: json['text'] as String,
      );
}
