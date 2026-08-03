import 'package:flutter_test/flutter_test.dart';
import 'package:scripturebuddy/features/game/game_models.dart';
import 'package:scripturebuddy/features/lessons/lesson_models.dart';

void main() {
  group('GameProgress', () {
    test('parses a full payload', () {
      final p = GameProgress.fromJson({
        'level': 3,
        'total_xp': 450,
        'xp_into_level': 133,
        'xp_to_next_level': 67,
        'fraction': 0.66,
        'streak': {
          'current': 5,
          'longest': 12,
          'freezes_available': 1,
          'practised_today': false,
          'at_risk': true,
        },
        'badges': [
          {'slug': 'a', 'title': 'A', 'description': 'x', 'earned': true},
          {'slug': 'b', 'title': 'B', 'description': 'y', 'earned': false},
        ],
      });
      expect(p.level, 3);
      expect(p.streak.current, 5);
      expect(p.streak.atRisk, isTrue);
      expect(p.badgesEarned, 1);
    });

    test('survives a sparse payload from a brand-new account', () {
      final p = GameProgress.fromJson({});
      expect(p.level, 1);
      expect(p.totalXp, 0);
      expect(p.streak.current, 0);
      expect(p.badges, isEmpty);
      expect(p.badgesEarned, 0);
    });
  });

  group('Rewards', () {
    test('parses badges and level-up', () {
      final r = Rewards.fromJson({
        'xp_awarded': 12,
        'total_xp': 120,
        'level': 2,
        'leveled_up': true,
        'streak': 3,
        'streak_extended': true,
        'new_badges': [
          {'slug': 'first-steps', 'title': 'First Steps', 'description': 'd'},
        ],
      });
      expect(r.xpAwarded, 12);
      expect(r.leveledUp, isTrue);
      expect(r.newBadges.single.title, 'First Steps');
    });

    test('an answer response without rewards degrades to empty', () {
      final result = AnswerResult.fromJson({
        'correct': true,
        'correct_answer': 'x',
        'explanation': '',
        'due_at': DateTime.now().toUtc().toIso8601String(),
      });
      expect(result.rewards.xpAwarded, 0);
      expect(result.rewards.newBadges, isEmpty);
    });

    test('rewards ride along on a normal answer response', () {
      final result = AnswerResult.fromJson({
        'correct': true,
        'correct_answer': 'x',
        'explanation': '',
        'due_at': DateTime.now().toUtc().toIso8601String(),
        'rewards': {'xp_awarded': 10, 'total_xp': 10, 'level': 1, 'streak': 1},
      });
      expect(result.rewards.xpAwarded, 10);
      expect(result.rewards.streak, 1);
    });
  });
}
