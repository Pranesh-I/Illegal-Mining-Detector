import 'package:flutter/material.dart';
import 'models/incident.dart';
import 'services/api_service.dart';

void main() {
  runApp(const MaterialApp(
    debugShowCheckedModeBanner: false,
    home: Dashboard(),
  ));
}

class Dashboard extends StatefulWidget {
  const Dashboard({super.key});

  @override
  State<Dashboard> createState() => _DashboardState();
}

class _DashboardState extends State<Dashboard> {
  final ApiService _api = ApiService();

  Incident? currentIncident;
  bool isLoading = false;

  void runScan() async {
    setState(() {
      isLoading = true;
      currentIncident = null;
    });

    print("📡 Calling Satellite API...");

    try {
      final incident =
          await _api.getLatestIncident(22.1067, 85.3868);

      setState(() {
        currentIncident = incident;
        isLoading = false;
      });

      if (incident == null) {
        print(
            "✅ Scan Complete: The forest is safe. No illegal activity detected.");

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text("Scan Complete: Area is Stable")),
        );
      } else {
        print("🚨 ALERT: Significant disturbance found!");
      }
    } catch (e) {
      setState(() => isLoading = false);

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Error occurred: $e")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Illegal Mining Detector"),
      ),
      body: Center(
        child: isLoading
            ? const Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 10),
                  Text("Analyzing Satellite Imagery..."),
                ],
              )
            : currentIncident == null
                ? const Text(
                    "✅ Area Clear: No Illegal Activity Detected",
                    style: TextStyle(fontSize: 18),
                  )
                : _buildReportUI(),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: runScan,
        child: const Icon(Icons.satellite_alt),
      ),
    );
  }

  Widget _buildReportUI() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Text(
            "Incident ID: ${currentIncident!.id}",
            style: const TextStyle(
                fontSize: 20, fontWeight: FontWeight.bold),
          ),
          Text(
            "Affected Area: ${currentIncident!.area.toStringAsFixed(2)} hectares",
          ),
          const SizedBox(height: 20),
          const Divider(),
          Row(
            children: [
              Expanded(
                child: _buildImage(currentIncident!.beforeUrl),
              ),
              const Icon(Icons.arrow_forward),
              Expanded(
                child: _buildImage(currentIncident!.afterUrl),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildImage(String url) {
    if (url == "NO_IMAGE_AVAILABLE") {
      return const Center(
        child: Text("No Image Available"),
      );
    }

    return Image.network(
      url,
      errorBuilder: (_, __, ___) {
        return const Text("Failed to load image");
      },
    );
  }
}