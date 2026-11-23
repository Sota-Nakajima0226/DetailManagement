import 'package:detail_management/core/navigation/app_location.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('root stays the main shell', () {
    final location = parseAppLocation(Uri.parse('https://example.com/'));
    expect(location.showsUpload, isFalse);
  });

  test('upload path keeps a valid year and month', () {
    final location = parseAppLocation(
      Uri.parse('/upload?year=2026&month=1'),
    );
    expect(location.showsUpload, isTrue);
    expect(location.year, 2026);
    expect(location.month, 1);
  });

  test('missing or invalid upload query leaves the date unset', () {
    final missing = parseAppLocation(Uri.parse('https://example.com/upload'));
    final oneSided = parseAppLocation(
      Uri.parse('https://example.com/upload?year=2026'),
    );
    final badMonth = parseAppLocation(
      Uri.parse('https://example.com/upload/?month=13&year=2026'),
    );

    for (final location in [missing, oneSided, badMonth]) {
      expect(location.showsUpload, isTrue);
      expect(location.year, isNull);
      expect(location.month, isNull);
    }
  });
}
