import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/incident.dart';

class ApiService {
  // IMPORTANT:
  // Emulator → use 10.0.2.2
  // Real phone → use PC local IP (example: 192.168.1.10)

  final String baseUrl = "http://127.0.0.1:8000";

  Future<Incident?> getLatestIncident(
      double lat, double lon) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/analyze'),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"lat": lat, "lon": lon}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        if (data['alert'] == true) {
          return Incident.fromJson(data);
        }

        return null;
      } else {
        print("Server error: ${response.statusCode}");
      }
    } catch (e) {
      print("Connection Error: $e");
    }

    return null;
  }
}