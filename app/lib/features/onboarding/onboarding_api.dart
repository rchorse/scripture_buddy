import 'dart:convert';

import 'package:amplify_auth_cognito/amplify_auth_cognito.dart';
import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:http/http.dart' as http;

import '../../core/config.dart';

/// Thrown with the server's own message, which is written for the reader
/// (e.g. "A parent or guardian needs to create this account for you").
class OnboardingApiException implements Exception {
  OnboardingApiException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// What the age gate decided. Nothing here is stored server-side — the gate is
/// deliberately anonymous, so a child who is turned away leaves no trace.
class AgeGateResult {
  AgeGateResult({
    required this.bracket,
    required this.canSelfRegister,
    required this.requiresParent,
    required this.message,
  });

  factory AgeGateResult.fromJson(Map<String, dynamic> json) => AgeGateResult(
        bracket: json['bracket'] as String? ?? '',
        canSelfRegister: json['can_self_register'] as bool? ?? false,
        requiresParent: json['requires_parent'] as bool? ?? false,
        message: json['message'] as String? ?? '',
      );

  final String bracket;
  final bool canSelfRegister;
  final bool requiresParent;
  final String message;
}

/// The signed-in user's profile.
class Me {
  Me({
    required this.username,
    required this.displayName,
    required this.bracket,
    required this.status,
    required this.needsRegistration,
    required this.isOwner,
  });

  factory Me.fromJson(Map<String, dynamic> json) => Me(
        username: json['username'] as String? ?? '',
        displayName: json['display_name'] as String? ?? '',
        bracket: json['bracket'] as String? ?? '',
        status: json['status'] as String? ?? '',
        needsRegistration: json['needs_registration'] as bool? ?? false,
        isOwner: json['is_owner'] as bool? ?? false,
      );

  final String username;
  final String displayName;
  final String bracket;
  final String status;
  final bool needsRegistration;
  final bool isOwner;
}

class OnboardingApi {
  Future<Map<String, String>> _headers({bool authed = true}) async {
    final headers = {'Content-Type': 'application/json'};
    if (authed) {
      final session = await Amplify.Auth.fetchAuthSession() as CognitoAuthSession;
      headers['Authorization'] =
          'Bearer ${session.userPoolTokensResult.value.idToken.raw}';
    }
    return headers;
  }

  Future<dynamic> _send(
    String method,
    String path, {
    Object? body,
    bool authed = true,
  }) async {
    final uri = Uri.parse('${AppConfig.apiUrl}$path');
    final headers = await _headers(authed: authed);
    final response = method == 'POST'
        ? await http.post(uri, headers: headers, body: jsonEncode(body))
        : await http.get(uri, headers: headers);
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
      throw OnboardingApiException(message);
    }
    return jsonDecode(response.body);
  }

  /// Unauthenticated by design — this runs before any account exists.
  Future<AgeGateResult> ageGate(DateTime birthDate) async => AgeGateResult.fromJson(
        await _send(
          'POST',
          '/v1/family/age-gate',
          body: {'birth_date': _isoDate(birthDate)},
          authed: false,
        ) as Map<String, dynamic>,
      );

  Future<Me> me() async =>
      Me.fromJson(await _send('GET', '/v1/me') as Map<String, dynamic>);

  /// Records the birth date the age gate collected. Write-once server-side.
  Future<void> register(DateTime birthDate, {String? displayName}) async {
    await _send('POST', '/v1/me/register', body: {
      'birth_date': _isoDate(birthDate),
      'timezone': await deviceTimezone(),
      if (displayName != null && displayName.isNotEmpty) 'display_name': displayName,
    });
  }

  /// The IANA name streak roll-over depends on. Falls back to UTC rather than
  /// guessing: a wrong zone silently breaks streaks at the day boundary.
  static Future<String> deviceTimezone() async {
    try {
      final name = (await FlutterTimezone.getLocalTimezone()).identifier;
      return name.isEmpty ? 'UTC' : name;
    } catch (_) {
      return 'UTC';
    }
  }

  static String _isoDate(DateTime date) =>
      '${date.year.toString().padLeft(4, '0')}-'
      '${date.month.toString().padLeft(2, '0')}-'
      '${date.day.toString().padLeft(2, '0')}';
}
