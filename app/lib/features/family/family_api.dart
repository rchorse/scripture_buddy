import 'dart:convert';

import 'package:amplify_auth_cognito/amplify_auth_cognito.dart';
import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:http/http.dart' as http;

import '../../core/config.dart';

class FamilyApiException implements Exception {
  FamilyApiException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// A child or parent in the household.
class FamilyMember {
  FamilyMember({
    required this.userId,
    required this.username,
    required this.displayName,
    required this.status,
    required this.bracket,
    required this.consents,
    required this.claimed,
  });

  factory FamilyMember.fromJson(Map<String, dynamic> json) => FamilyMember(
        userId: json['user_id'] as String? ?? '',
        username: json['username'] as String? ?? '',
        displayName: json['display_name'] as String? ?? '',
        status: json['status'] as String? ?? '',
        bracket: json['bracket'] as String? ?? '',
        consents:
            (json['consents'] as List?)?.map((e) => '$e').toList() ?? const [],
        claimed: json['claimed'] as bool? ?? false,
      );

  final String userId;
  final String username;
  final String displayName;
  final String status;
  final String bracket;
  final List<String> consents;

  /// False until the child has signed in for the first time and taken over the
  /// row their parent created.
  final bool claimed;

  bool get awaitingConsent => status == 'pending_consent';
  bool get isUnder13 => bracket == 'under_13';
}

class FamilyState {
  FamilyState({required this.role, required this.children, required this.parents});

  factory FamilyState.fromJson(Map<String, dynamic> json) => FamilyState(
        role: json['role'] as String? ?? '',
        children: ((json['children'] as List?) ?? [])
            .map((e) => FamilyMember.fromJson(e as Map<String, dynamic>))
            .toList(),
        parents: ((json['parents'] as List?) ?? [])
            .map((e) => FamilyMember.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  final String role;
  final List<FamilyMember> children;
  final List<FamilyMember> parents;
}

class FamilyApi {
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
      throw FamilyApiException(message);
    }
    return jsonDecode(response.body);
  }

  Future<FamilyState> me() async =>
      FamilyState.fromJson(await _send('GET', '/v1/family') as Map<String, dynamic>);

  /// Creates the child's account. Only a username, birth date and timezone are
  /// sent — there is deliberately no email, phone or real-name field for a
  /// minor anywhere in this app.
  Future<Map<String, dynamic>> addChild({
    required String username,
    required DateTime birthDate,
    String displayName = '',
    bool allowAiProcessing = true,
    bool allowSocial = false,
    String? timezone,
  }) async =>
      await _send('POST', '/v1/family/children', {
        'username': username,
        'birth_date': '${birthDate.year.toString().padLeft(4, '0')}-'
            '${birthDate.month.toString().padLeft(2, '0')}-'
            '${birthDate.day.toString().padLeft(2, '0')}',
        'display_name': displayName,
        'allow_ai_processing': allowAiProcessing,
        'allow_social': allowSocial,
        if (timezone != null) 'timezone': timezone,
      }) as Map<String, dynamic>;

  /// The child signs in with username + password only, so the parent is the one
  /// who sets it — there is no email on the account to reset it with.
  Future<void> setChildPassword(String childId, String password) async =>
      _send('POST', '/v1/family/children/$childId/set-password', {
        'password': password,
      });

  Future<void> revokeConsent(String consentId) async =>
      _send('POST', '/v1/family/consents/$consentId/revoke');

  Future<Map<String, dynamic>> deleteChild(String childId) async =>
      await _send('POST', '/v1/family/children/$childId/delete')
          as Map<String, dynamic>;

  Future<void> cancelDeletion(String childId) async =>
      _send('POST', '/v1/family/children/$childId/cancel-deletion');
}
