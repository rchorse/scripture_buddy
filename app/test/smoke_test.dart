import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:scripturebuddy/features/onboarding/sign_in_page.dart';

void main() {
  testWidgets('sign-in page renders', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: SignInPage()));
    expect(find.text('ScriptureBuddy'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(2));
    expect(find.text('Sign in'), findsOneWidget);
  });
}
