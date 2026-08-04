import 'dart:convert';

import 'package:amplify_auth_cognito/amplify_auth_cognito.dart';
import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:http/http.dart' as http;

import '../../core/config.dart';
import 'social_models.dart';

/// Thrown with the server's own message, which is written for the learner
/// (e.g. "A parent must consent to friends and leaderboards for this account").
class SocialApiException implements Exception {
  SocialApiException(this.message);
  final String message;
  @override
  String toString() => message;
}

class SocialApi {
  Future<Map<String, String>> _headers() async {
    final session = await Amplify.Auth.fetchAuthSession() as CognitoAuthSession;
    final token = session.userPoolTokensResult.value.idToken.raw;
    return {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'};
  }

  Future<dynamic> _send(String method, String path, [Object? body]) async {
    final uri = Uri.parse('${AppConfig.apiUrl}$path');
    final headers = await _headers();
    final response = switch (method) {
      'POST' => await http.post(uri, headers: headers, body: jsonEncode(body)),
      'PUT' => await http.put(uri, headers: headers, body: jsonEncode(body)),
      'DELETE' => await http.delete(uri, headers: headers),
      _ => await http.get(uri, headers: headers),
    };
    if (response.statusCode >= 400) {
      String message = 'Something went wrong (${response.statusCode}).';
      try {
        final decoded = jsonDecode(response.body);
        if (decoded is Map && decoded['detail'] is String) {
          message = decoded['detail'] as String;
        }
      } catch (_) {
        // Keep the generic message.
      }
      throw SocialApiException(message);
    }
    return jsonDecode(response.body);
  }

  Future<SocialState> me() async =>
      SocialState.fromJson(await _send('GET', '/v1/social/me') as Map<String, dynamic>);

  Future<Map<String, dynamic>> setDisplayName(String name) async =>
      await _send('PUT', '/v1/social/display-name', {'display_name': name})
          as Map<String, dynamic>;

  Future<void> sendRequest(String username) async =>
      _send('POST', '/v1/social/requests', {'username': username});

  Future<String> accept(String requestId) async {
    final body =
        await _send('POST', '/v1/social/requests/$requestId/accept') as Map<String, dynamic>;
    return body['note'] as String? ?? '';
  }

  Future<void> decline(String requestId) async =>
      _send('POST', '/v1/social/requests/$requestId/decline');

  Future<void> unfriend(String userId) async =>
      _send('DELETE', '/v1/social/friends/$userId');

  Future<void> block(String userId) async =>
      _send('POST', '/v1/social/blocks', {'user_id': userId});

  Future<List<PendingApproval>> pendingApprovals() async {
    final body = await _send('GET', '/v1/social/approvals') as List;
    return body
        .map((a) => PendingApproval.fromJson(a as Map<String, dynamic>))
        .toList();
  }

  Future<void> decideApproval(String approvalId, bool approve) async =>
      _send('POST', '/v1/social/approvals/$approvalId', {'approve': approve});

  Future<Standings> league() async =>
      Standings.fromJson(await _send('GET', '/v1/social/league') as Map<String, dynamic>);

  Future<Standings> leaderboard() async => Standings.fromJson(
      await _send('GET', '/v1/social/leaderboard') as Map<String, dynamic>);
}
