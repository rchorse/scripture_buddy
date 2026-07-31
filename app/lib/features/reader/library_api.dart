import 'dart:convert';

import 'package:amplify_auth_cognito/amplify_auth_cognito.dart';
import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:http/http.dart' as http;

import '../../core/config.dart';
import 'library_models.dart';

/// API calls for the library/reader feature.
class LibraryApi {
  Future<Map<String, String>> _headers() async {
    final session = await Amplify.Auth.fetchAuthSession() as CognitoAuthSession;
    final token = session.userPoolTokensResult.value.idToken.raw;
    return {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'};
  }

  Future<dynamic> _get(String path) async {
    final response =
        await http.get(Uri.parse('${AppConfig.apiUrl}$path'), headers: await _headers());
    if (response.statusCode >= 400) {
      throw Exception('GET $path failed (${response.statusCode})');
    }
    return jsonDecode(response.body);
  }

  Future<List<WorkSummary>> listWorks() async {
    final body = await _get('/v1/library/works') as List;
    return body.map((w) => WorkSummary.fromJson(w as Map<String, dynamic>)).toList();
  }

  Future<List<BookToc>> tableOfContents(String slug) async {
    final body = await _get('/v1/library/works/$slug/toc') as Map<String, dynamic>;
    return (body['books'] as List)
        .map((b) => BookToc.fromJson(b as Map<String, dynamic>))
        .toList();
  }

  Future<List<VerseText>> verses(String divisionId) async {
    final body = await _get('/v1/library/divisions/$divisionId/verses') as List;
    return body.map((v) => VerseText.fromJson(v as Map<String, dynamic>)).toList();
  }

  Future<String?> readingPosition(String slug) async {
    final body = await _get('/v1/library/works/$slug/position') as Map<String, dynamic>;
    return body['division_id'] as String?;
  }

  Future<void> savePosition(String slug, String divisionId, int versePosition) async {
    final response = await http.put(
      Uri.parse('${AppConfig.apiUrl}/v1/library/works/$slug/position'),
      headers: await _headers(),
      body: jsonEncode({'division_id': divisionId, 'verse_position': versePosition}),
    );
    if (response.statusCode >= 400) {
      throw Exception('save position failed (${response.statusCode})');
    }
  }
}
