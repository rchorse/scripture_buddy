import 'package:amplify_auth_cognito/amplify_auth_cognito.dart';
import 'package:amplify_flutter/amplify_flutter.dart';

/// Sign-in options used everywhere in the app.
///
/// Forces USER_PASSWORD_AUTH instead of Amplify's default SRP.
///
/// This user pool has `email` as an alias attribute, so Cognito's SRP challenge
/// comes back with `USER_ID_FOR_SRP` (the sub) rather than the username, and
/// Amplify's Dart SRP implementation wedges on it: no request is issued and the
/// future never completes. Isolated to a single variable — the same account,
/// same password, signs in fine the moment its `email` attribute is removed and
/// hangs again when it is restored.
///
/// `AliasAttributes` cannot be changed after a pool is created, so the alias is
/// not going away without migrating every user to a new pool.
///
/// The trade-off: USER_PASSWORD_AUTH sends the password to Cognito inside the
/// TLS session instead of proving knowledge of it via SRP. Cognito is the party
/// that would receive it either way and nothing else can read it, but it is a
/// real reduction from SRP's guarantee, taken because the alternative is an app
/// nobody can sign in to.
const signInOptions = SignInOptions(
  pluginOptions: CognitoSignInPluginOptions(
    authFlowType: AuthenticationFlowType.userPasswordAuth,
  ),
);
