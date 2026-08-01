import 'package:flutter_test/flutter_test.dart';
import 'package:scripturebuddy/features/lessons/lesson_models.dart';

AnswerResult resultDueIn(Duration delta) => AnswerResult(
      correct: true,
      correctAnswer: 'x',
      explanation: '',
      dueAt: DateTime.now().toUtc().add(delta),
    );

void main() {
  group('nextReviewLabel', () {
    test('rounds days rather than truncating', () {
      // A card scheduled exactly 3 days out must not read "2 days" because a
      // few milliseconds elapsed between scheduling and rendering.
      expect(
        resultDueIn(const Duration(days: 3) - const Duration(seconds: 2))
            .nextReviewLabel,
        'Back in 3 days',
      );
    });

    test('rounds hours rather than truncating', () {
      expect(
        resultDueIn(const Duration(minutes: 237)).nextReviewLabel,
        'Back in 4 hours',
      );
    });

    test('singular hour', () {
      expect(
        resultDueIn(const Duration(minutes: 62)).nextReviewLabel,
        'Back in 1 hour',
      );
    });

    test('minutes under an hour', () {
      expect(
        resultDueIn(const Duration(minutes: 25)).nextReviewLabel,
        'Back in 25 min',
      );
    });
  });

  group('ExerciseView', () {
    test('cloze prompt uses display text and carries no answer field', () {
      final view = ExerciseView.fromJson({
        'id': 'e1',
        'kind': 'cloze',
        'verse_ref': '1 Nephi 3:7',
        'display_text': 'I will ____',
        'options': ['go and do', 'wait', 'flee', 'ask'],
      });
      expect(view.prompt, 'I will ____');
      expect(view.options.length, 4);
    });

    test('mcq prompt uses the question', () {
      final view = ExerciseView.fromJson({
        'id': 'e2',
        'kind': 'mcq',
        'question': 'What did Nephi say?',
        'options': ['a', 'b', 'c', 'd'],
      });
      expect(view.prompt, 'What did Nephi say?');
    });

    test('review queue payloads use exercise_id', () {
      final view = ExerciseView.fromJson({
        'exercise_id': 'e3',
        'kind': 'mcq',
        'question': 'q',
        'options': ['a', 'b'],
        'lesson_title': '1 Nephi 3 — Chapter quiz',
      });
      expect(view.id, 'e3');
      expect(view.lessonTitle, '1 Nephi 3 — Chapter quiz');
    });
  });
}
