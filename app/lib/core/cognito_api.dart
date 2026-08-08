import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';

/// Cognito's unauthenticated endpoints, called directly over HTTPS.
///
/// Amplify's `signUp` hangs on web: it spawns its worker and then never issues
/// a request, so the future neither completes nor throws. Verified from the
/// running page that the same call as a plain POST returns 200 and creates the
/// user, which rules out CORS, the client id, the password policy and the
/// network — the wedge is inside Amplify.
///
/// These five operations need nothing but the app client id, so there is
/// nothing Amplify was doing for us here worth the risk. Sign-in stays on
/// Amplify: it works, it does SRP so the password never crosses the wire, and
/// it owns the session that the rest of the app reads.
class CognitoApi {
  CognitoApi({http.Client? inner}) : _inner = inner ?? http.Client();

  final http.Client _inner;

  /// `us-west-2_xCiNl2VUM` -> `us-west-2`.
  static String get region => AppConfig.userPoolId.split('_').first;

  static Uri get _endpoint =>
      Uri.parse('https://cognito-idp.$region.amazonaws.com/');

  Future<Map<String, dynamic>> _call(String action, Map<String, Object?> body) async {
    final response = await _inner.post(
      _endpoint,
      headers: {
        'Content-Type': 'application/x-amz-json-1.1',
        'X-Amz-Target': 'AWSCognitoIdentityProviderService.$action',
      },
      body: jsonEncode({'ClientId': AppConfig.userPoolClientId, ...body}),
    );
    final decoded = response.body.isEmpty
        ? <String, dynamic>{}
        : jsonDecode(response.body) as Map<String, dynamic>;
    if (response.statusCode >= 400) {
      throw CognitoException(
        // `__type` looks like "UsernameExistsException" or a full ARN-ish
        // string; the trailing segment is the part worth showing.
        (decoded['__type'] as String? ?? 'UnknownError').split('#').last,
        decoded['message'] as String? ??
            decoded['Message'] as String? ??
            'Something went wrong (${response.statusCode}).',
      );
    }
    return decoded;
  }

  Future<void> signUp({
    required String username,
    required String password,
    required String email,
  }) =>
      _call('SignUp', {
        'Username': username,
        'Password': password,
        'UserAttributes': [
          {'Name': 'email', 'Value': email},
        ],
      });

  Future<void> confirmSignUp({
    required String username,
    required String code,
  }) =>
      _call('ConfirmSignUp', {
        'Username': username,
        'ConfirmationCode': code,
      });

  Future<void> resendCode(String username) =>
      _call('ResendConfirmationCode', {'Username': username});

  Future<void> forgotPassword(String username) =>
      _call('ForgotPassword', {'Username': username});

  Future<void> confirmForgotPassword({
    required String username,
    required String code,
    required String newPassword,
  }) =>
      _call('ConfirmForgotPassword', {
        'Username': username,
        'ConfirmationCode': code,
        'Password': newPassword,
      });
}

class CognitoException implements Exception {
  CognitoException(this.code, this.message);

  final String code;
  final String message;

  /// True when the account exists already — the caller usually wants to send
  /// the reader to sign-in rather than show this as a failure.
  bool get isAlreadyExists => code == 'UsernameExistsException';

  @override
  String toString() => message;
}
