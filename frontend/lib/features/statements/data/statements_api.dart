import 'package:dio/dio.dart';

import '../../../core/config/app_config.dart';
import '../../upload/models/upload_result.dart';
import '../models/category_item.dart';
import '../models/statement_item.dart';

class StatementsApi {
  StatementsApi() : _dio = Dio(BaseOptions(baseUrl: AppConfig.apiBaseUrl));

  final Dio _dio;

  List<Map<String, dynamic>> _asMapList(List<dynamic>? data) {
    return (data ?? <dynamic>[])
        .map((item) => item as Map<String, dynamic>)
        .toList();
  }

  Future<List<CategoryItem>> fetchCategories() async {
    final response = await _dio.get<List<dynamic>>('/categories');
    final data = response.data ?? <dynamic>[];
    return data
        .map((item) => CategoryItem.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<List<StatementItem>> fetchStatements({
    required int year,
    required int month,
    int? categoryId,
    String? cardHolder,
    bool? isUnclassified,
  }) async {
    final query = <String, dynamic>{
      'year': year,
      'month': month,
    };
    if (categoryId != null) {
      query['category'] = categoryId;
    }
    if (cardHolder != null && cardHolder.isNotEmpty) {
      query['card_holder'] = cardHolder;
    }
    if (isUnclassified != null) {
      query['is_unclassified'] = isUnclassified;
    }

    final response = await _dio.get<List<dynamic>>(
      '/statements',
      queryParameters: query,
    );
    final data = response.data ?? <dynamic>[];
    return data
        .map((item) => StatementItem.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<StatementItem> updateStatementCategory({
    required int statementItemId,
    required int categoryId,
  }) async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '/statements/items/$statementItemId',
      data: <String, dynamic>{'category_id': categoryId},
    );
    final data = response.data;
    if (data == null) {
      throw Exception('カテゴリ更新レスポンスが空です');
    }
    return StatementItem.fromJson(data);
  }

  Future<bool> hasStatementsInMonth({
    required int year,
    required int month,
  }) async {
    final items = await fetchStatements(year: year, month: month);
    return items.isNotEmpty;
  }

  Future<UploadResult> uploadStatement({
    required String fileName,
    required List<int> fileBytes,
    required int year,
    required int month,
  }) async {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(fileBytes, filename: fileName),
      'year': year.toString(),
      'month': month.toString(),
    });
    final response = await _dio.post<Map<String, dynamic>>(
      '/statements/upload',
      data: formData,
    );
    final data = response.data;
    if (data == null) {
      throw Exception('アップロード結果が空です');
    }
    return UploadResult.fromJson(data);
  }

  Future<Map<String, dynamic>> fetchCategorySummary({
    required int year,
    required int month,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/statements/summary',
      queryParameters: {'year': year, 'month': month},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> fetchHolderSummary({
    required int year,
    required int month,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/statements/summary/by-holder',
      queryParameters: {'year': year, 'month': month},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> fetchMonthlyTrend({
    required int fromYear,
    required int fromMonth,
    required int toYear,
    required int toMonth,
    int? categoryId,
  }) async {
    final query = <String, dynamic>{
      'from_year': fromYear,
      'from_month': fromMonth,
      'to_year': toYear,
      'to_month': toMonth,
    };
    if (categoryId != null) {
      query['category_id'] = categoryId;
    }
    final response = await _dio.get<Map<String, dynamic>>(
      '/statements/summary/monthly-trend',
      queryParameters: query,
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<List<Map<String, dynamic>>> fetchCategoriesRaw() async {
    final response = await _dio.get<List<dynamic>>('/categories');
    return _asMapList(response.data);
  }

  Future<Map<String, dynamic>> createCategory({
    required String name,
    required String color,
    required int sortOrder,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/categories',
      data: {
        'name': name,
        'color': color,
        'sort_order': sortOrder,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateCategory({
    required int id,
    required String name,
    required String color,
    required int sortOrder,
  }) async {
    final response = await _dio.put<Map<String, dynamic>>(
      '/categories/$id',
      data: {
        'name': name,
        'color': color,
        'sort_order': sortOrder,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<void> deleteCategory(int id) async {
    await _dio.delete<void>('/categories/$id');
  }

  Future<List<Map<String, dynamic>>> fetchRules() async {
    final response = await _dio.get<List<dynamic>>('/rules');
    return _asMapList(response.data);
  }

  Future<Map<String, dynamic>> createRule({
    required String pattern,
    required bool isRegex,
    required int categoryId,
    required int priority,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/rules',
      data: {
        'pattern': pattern,
        'is_regex': isRegex,
        'category_id': categoryId,
        'priority': priority,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateRule({
    required int id,
    required String pattern,
    required bool isRegex,
    required int categoryId,
    required int priority,
  }) async {
    final response = await _dio.put<Map<String, dynamic>>(
      '/rules/$id',
      data: {
        'pattern': pattern,
        'is_regex': isRegex,
        'category_id': categoryId,
        'priority': priority,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<void> deleteRule(int id) async {
    await _dio.delete<void>('/rules/$id');
  }

  Future<List<Map<String, dynamic>>> fetchFixedExpenses() async {
    final response = await _dio.get<List<dynamic>>('/fixed-expenses');
    return _asMapList(response.data);
  }

  Future<Map<String, dynamic>> createFixedExpense(Map<String, dynamic> payload) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/fixed-expenses',
      data: payload,
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateFixedExpense(
    int id,
    Map<String, dynamic> payload,
  ) async {
    final response = await _dio.put<Map<String, dynamic>>(
      '/fixed-expenses/$id',
      data: payload,
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<void> disableFixedExpense(int id) async {
    await _dio.delete<void>('/fixed-expenses/$id');
  }

  Future<List<Map<String, dynamic>>> fetchManualExpenses({
    int? year,
    int? month,
  }) async {
    final query = <String, dynamic>{};
    if (year != null) query['year'] = year;
    if (month != null) query['month'] = month;
    final response = await _dio.get<List<dynamic>>(
      '/manual-expenses',
      queryParameters: query,
    );
    return _asMapList(response.data);
  }

  Future<Map<String, dynamic>> createManualExpense(Map<String, dynamic> payload) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/manual-expenses',
      data: payload,
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateManualExpense(
    int id,
    Map<String, dynamic> payload,
  ) async {
    final response = await _dio.put<Map<String, dynamic>>(
      '/manual-expenses/$id',
      data: payload,
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<void> deleteManualExpense(int id) async {
    await _dio.delete<void>('/manual-expenses/$id');
  }
}
