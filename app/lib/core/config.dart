/// Build-time configuration, injected via --dart-define.
class AppConfig {
  static const apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://localhost:8000',
  );
  static const userPoolId = String.fromEnvironment('USER_POOL_ID');
  static const userPoolClientId = String.fromEnvironment('USER_POOL_CLIENT_ID');
}
