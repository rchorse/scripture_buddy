import 'package:web/web.dart' as web;

/// Opens [url] in a new tab.
Future<bool> openUrl(String url) async {
  web.window.open(url, '_blank');
  return true;
}
