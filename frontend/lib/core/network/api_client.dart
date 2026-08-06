import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../config/app_config.dart';

typedef AccessTokenProvider = String? Function();
typedef UnauthorizedHandler = Future<void> Function();

class ApiClient {
  ApiClient({
    required AccessTokenProvider accessTokenProvider,
    UnauthorizedHandler? onUnauthorized,
  })  : _accessTokenProvider = accessTokenProvider,
        _onUnauthorized = onUnauthorized,
        dio = Dio(
          BaseOptions(
            baseUrl: AppConfig.apiBaseUrl,
            connectTimeout: const Duration(seconds: 30),
            receiveTimeout: const Duration(seconds: 30),
          ),
        ) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final token = _accessTokenProvider();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (error, handler) async {
          final response = error.response;
          if (response?.statusCode == 401) {
            await _onUnauthorized?.call();
          } else if (response?.statusCode == 403) {
            _showForbiddenMessage(response);
          }
          handler.next(error);
        },
      ),
    );
  }

  final Dio dio;
  final AccessTokenProvider _accessTokenProvider;
  final UnauthorizedHandler? _onUnauthorized;

  static final GlobalKey<ScaffoldMessengerState> scaffoldMessengerKey =
      GlobalKey<ScaffoldMessengerState>();

  void _showForbiddenMessage(Response<dynamic>? response) {
    final detail = response?.data;
    var message = 'このアプリに登録されていないユーザーです。';
    if (detail is Map && detail['detail'] is String) {
      message = detail['detail'] as String;
    }
    final messenger = scaffoldMessengerKey.currentState;
    if (messenger != null) {
      messenger.showSnackBar(SnackBar(content: Text(message)));
    }
  }
}
