import 'package:flutter/material.dart';

import '../presentation/auth_gate.dart';
import 'app_location.dart';

Route<void> buildAppRoute(RouteSettings settings) {
  final location = parseAppLocation(Uri.parse(settings.name ?? '/'));
  return MaterialPageRoute<void>(
    settings: settings,
    builder: (_) => AuthGate(location: location),
  );
}

List<Route<void>> buildInitialAppRoutes(String initialRoute) {
  return <Route<void>>[
    buildAppRoute(RouteSettings(name: initialRoute)),
  ];
}
