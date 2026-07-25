import 'package:amplify_auth_cognito/amplify_auth_cognito.dart';
import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/config.dart';
import 'features/onboarding/sign_in_page.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await _configureAmplify();
  runApp(const ProviderScope(child: ScriptureBuddyApp()));
}

Future<void> _configureAmplify() async {
  if (Amplify.isConfigured) return;
  await Amplify.addPlugin(AmplifyAuthCognito());
  final config = '''
{
  "auth": {
    "user_pool_id": "${AppConfig.userPoolId}",
    "user_pool_client_id": "${AppConfig.userPoolClientId}",
    "aws_region": "us-west-2",
    "username_attributes": [],
    "user_verification_types": []
  },
  "version": "2"
}
''';
  await Amplify.configure(config);
}

class ScriptureBuddyApp extends StatelessWidget {
  const ScriptureBuddyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ScriptureBuddy',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2E7D32)),
        useMaterial3: true,
      ),
      home: const SignInPage(),
    );
  }
}
