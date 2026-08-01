import 'dart:convert';

import 'package:amplify_auth_cognito/amplify_auth_cognito.dart';
import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:http/http.dart' as http;

import '../../core/config.dart';
import 'lesson_models.dart';

class LessonsApi {
  Future<Map<String, String>> _headers() async {
    final session = await Amplify.Auth.fetchAuthSession() as CognitoAuthSession;
    final token = session.userPoolTokensResult.value.idToken.raw;
    return {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'};
  }

  Future<dynamic> _send(String method, String path, [Object? body]) async {
    final uri = Uri.parse('${AppConfig.apiUrl}$path');
    final headers = await _headers();
    final response = method == 'POST'
        ? await http.post(uri, headers: headers, body: jsonEncode(body))
        : await http.get(uri, headers: headers);
    if (response.statusCode >= 400) {
      throw Exception('$method $path failed (${response.statusCode})');
    }
    return jsonDecode(response.body);
  }

  Future<List<LessonSummary>> lessonsForChapter(String divisionId) async {
    final body = await _send('GET', '/v1/lessons/by-division/$divisionId') as List;
    return body
        .map((l) => LessonSummary.fromJson(l as Map<String, dynamic>))
        .toList();
  }

  Future<List<ExerciseView>> exercises(String lessonId) async {
    final body = await _send('GET', '/v1/lessons/$lessonId/exercises') as List;
    return body
        .map((e) => ExerciseView.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<ExerciseView>> dueReviews({int limit = 20}) async {
    final body = await _send('GET', '/v1/reviews/due?limit=$limit') as List;
    return body
        .map((e) => ExerciseView.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<AnswerResult> answer(String exerciseId, String choice) async {
    final body = await _send(
      'POST',
      '/v1/exercises/$exerciseId/answer',
      {'answer': choice},
    ) as Map<String, dynamic>;
    return AnswerResult.fromJson(body);
  }

  Future<void> flag(String exerciseId, String reason, String note) async {
    await _send('POST', '/v1/lessons/exercises/$exerciseId/flag', {
      'reason': reason,
      'note': note,
    });
  }
}
