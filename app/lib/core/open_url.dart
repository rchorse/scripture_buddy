import 'package:url_launcher/url_launcher.dart';

import 'config.dart';

/// Opens an external page.
///
/// Used for the privacy policy, which both stores expect reachable from inside
/// the app. This went through a web-only stub first, which meant the link was a
/// dead button on Android — the platform where the stores actually check.
///
/// A relative path is resolved against the web origin so the same call works on
/// mobile, where there is no origin to be relative to.
Future<bool> openUrl(String path) async {
  final url = path.startsWith('http') ? path : '${AppConfig.webUrl}$path';
  return launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
}
