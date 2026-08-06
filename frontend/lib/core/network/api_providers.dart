import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/auth/application/auth_providers.dart';
import '../../features/statements/data/statements_api.dart';
import 'api_client.dart';

final apiClientProvider = Provider<ApiClient>((ref) {
  final authRepository = ref.watch(authRepositoryProvider);
  return ApiClient(
    accessTokenProvider: () => authRepository.currentAccessToken,
    onUnauthorized: authRepository.signOut,
  );
});

final statementsApiProvider = Provider<StatementsApi>((ref) {
  return StatementsApi(ref.watch(apiClientProvider).dio);
});
