class Incident {
  final String id;
  final double lat;
  final double lon;
  final double area;
  final String beforeUrl;
  final String afterUrl;

  Incident({
    required this.id,
    required this.lat,
    required this.lon,
    required this.area,
    required this.beforeUrl,
    required this.afterUrl,
  });

  factory Incident.fromJson(Map<String, dynamic> json) {
    return Incident(
      id: json['incident_id'] ?? "UNKNOWN",

      lat: (json['coordinates']?['lat'] ?? 0).toDouble(),

      lon: (json['coordinates']?['lon'] ?? 0).toDouble(),

      area:
          (json['area_hectares'] ?? 0).toDouble(),

      beforeUrl:
          json['evidence']?['before'] ??
              "NO_IMAGE_AVAILABLE",

      afterUrl:
          json['evidence']?['after'] ??
              "NO_IMAGE_AVAILABLE",
    );
  }
}