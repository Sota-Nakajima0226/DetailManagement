class CardIssuer {
  const CardIssuer({
    required this.id,
    required this.code,
    required this.displayName,
    required this.isActive,
    required this.includeInReminder,
    required this.remindDayOfMonth,
    required this.sortOrder,
  });

  final int id;
  final String code;
  final String displayName;
  final bool isActive;
  final bool includeInReminder;
  final int remindDayOfMonth;
  final int sortOrder;

  factory CardIssuer.fromJson(Map<String, dynamic> json) {
    return CardIssuer(
      id: json['id'] as int,
      code: json['code'] as String,
      displayName: json['display_name'] as String,
      isActive: json['is_active'] as bool? ?? true,
      includeInReminder: json['include_in_reminder'] as bool? ?? true,
      remindDayOfMonth: json['remind_day_of_month'] as int? ?? 1,
      sortOrder: json['sort_order'] as int? ?? 0,
    );
  }
}
