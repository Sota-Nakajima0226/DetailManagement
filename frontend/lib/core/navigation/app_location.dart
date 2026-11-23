/// ブラウザのパスから、最初に開く画面を決める。
class AppLocation {
  const AppLocation.shell()
      : showsUpload = false,
        year = null,
        month = null;

  const AppLocation.upload({
    this.year,
    this.month,
  }) : showsUpload = true;

  final bool showsUpload;
  final int? year;
  final int? month;
}

/// `/upload` はアップロード画面。`year` と `month` が両方そろい、月が 1〜12 のときだけ初期値にする。
AppLocation parseAppLocation(Uri uri) {
  final path = _normalizePath(uri.path);
  if (path != '/upload') {
    return const AppLocation.shell();
  }

  final yearText = uri.queryParameters['year'];
  final monthText = uri.queryParameters['month'];
  if (yearText == null && monthText == null) {
    return const AppLocation.upload();
  }

  final year = int.tryParse(yearText ?? '');
  final month = int.tryParse(monthText ?? '');
  if (year == null || month == null || month < 1 || month > 12) {
    return const AppLocation.upload();
  }
  return AppLocation.upload(year: year, month: month);
}

String _normalizePath(String path) {
  if (path.length > 1 && path.endsWith('/')) {
    return path.substring(0, path.length - 1);
  }
  return path;
}
