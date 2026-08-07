import 'package:flutter/material.dart';

/// The under-13 dead end.
///
/// This deliberately offers no way forward. Showing a signup form to a child —
/// even one that would later ask for a parent's email — would collect personal
/// information from a child before verifiable parental consent, which is the
/// thing COPPA prohibits. The parent starts the account from their own device,
/// signed in as themselves.
class ParentRequiredPage extends StatelessWidget {
  const ParentRequiredPage({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Ask a grown-up')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 380),
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.family_restroom, size: 64),
                const SizedBox(height: 24),
                Text(
                  message.isEmpty
                      ? 'A parent or guardian needs to create this account for you.'
                      : message,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 16),
                Text(
                  'Ask them to make their own ScriptureBuddy account first, then '
                  'add you to their family from the Family screen.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 32),
                OutlinedButton(
                  onPressed: () => Navigator.of(context)
                      .popUntil((route) => route.isFirst),
                  child: const Text('Back to sign in'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
