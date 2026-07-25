import 'dart:convert';

import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:http/http.dart' as http;

import 'config.dart';

/// Thin authenticated HTTP client for the ScriptureBuddy API.
class ApiClient {
  ApiClient({http.Client? inner}) : _inner = inner ?? http.Client();

  final http.Client _inner;

  Future<Map<String, dynamic>> getJson(String path) async {
    final response = await _inner.get(
      Uri.parse('${AppConfig.apiUrl}$path'),
      headers: await _headers(),
    );
    if (response.statusCode >= 400) {
      throw ApiException(response.statusCode, response.body);
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, String>> _headers() async {
    final session = await Amplify.Auth.fetchAuthSession() as CognitoAuthSession;
    final token = session.userPoolTokensResult.value.idToken.raw;
    return {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };
  }
}

class ApiException implements Exception {
  ApiException(this.statusCode, this.body);

  final int statusCode;
  final String body;

  @override
  String toString() => 'ApiException($statusCode): $body';
}
