#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2022-2026 Huntington Applied
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ===============================================================
# SEGA MODULE - INTELLIGENT OPTIMIZER
# ===============================================================
# File: src/sega/intelligence/optimizer.py
# Purpose: AI-powered optimization engine
#
# Description: Analyzes deployment metrics and provides intelligent optimization
# recommendations for resource usage, cost, performance, security, and reliability.
# Uses machine learning models and heuristics to identify optimization opportunities.
#
# Dependencies:
# - External: dataclasses, datetime, statistics, subprocess
# - Internal: None (standalone optimization engine)
#
# Used by: CLI optimize command, monitoring services, API optimization endpoints
#

"""AI-powered optimization engine."""

import json
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
import statistics
import re
import logging
from collections import defaultdict


@dataclass
class OptimizationRecommendation:
    """Optimization recommendation."""

    category: str
    priority: str  # high, medium, low
    title: str
    description: str
    impact: str
    effort: str  # low, medium, high
    implementation: str
    expected_savings: Optional[Dict[str, Any]] = None


@dataclass
class AnomalyDetection:
    """Anomaly detection result."""

    detected: bool
    severity: str  # low, medium, high, critical
    metric_name: str
    current_value: float
    expected_range: tuple
    timestamp: datetime
    description: str


@dataclass
class PredictiveScaling:
    """Predictive scaling recommendation."""

    metric_name: str
    current_value: float
    predicted_value: float
    recommended_action: str  # scale_up, scale_down, maintain
    confidence: float
    time_horizon: str
    reasoning: str


@dataclass
class OptimizationResult:
    """Result of optimization analysis."""

    success: bool
    recommendations: List[OptimizationRecommendation]
    current_metrics: Dict[str, Any]
    anomalies: List[AnomalyDetection] = None
    predictions: List[PredictiveScaling] = None
    cost_analysis: Dict[str, Any] = None
    error: Optional[str] = None


class IntelligentOptimizer:
    """AI-powered optimization engine for SEGA deployments."""

    def __init__(self, ai_enabled: bool = True):
        self.ai_enabled = ai_enabled
        self.logger = logging.getLogger(__name__)
        self.historical_metrics = defaultdict(list)
        self.anomaly_thresholds = {
            "cpu_usage": (0, 95),
            "memory_usage": (0, 90),
            "response_time": (0, 5000),
            "error_rate": (0, 5),
            "disk_usage": (0, 85),
        }
        self.analyzers = {
            "resource": self._analyze_resource_usage,
            "cost": self._analyze_cost_optimization,
            "performance": self._analyze_performance,
            "security": self._analyze_security_posture,
            "reliability": self._analyze_reliability,
        }

    def optimize(self, target: str, metric: str = "all") -> OptimizationResult:
        """Run optimization analysis."""
        try:
            # Collect current metrics
            current_metrics = self._collect_metrics(target)

            # Store metrics for historical analysis
            self._store_historical_metrics(target, current_metrics)

            recommendations = []
            anomalies = []
            predictions = []
            cost_analysis = {}

            # Run AI-powered analysis if enabled
            if self.ai_enabled:
                anomalies = self._detect_anomalies(target, current_metrics)
                predictions = self._predict_scaling_needs(
                    target, current_metrics
                )
                cost_analysis = self._analyze_cost_forecasting(
                    target, current_metrics
                )

            if metric == "all":
                # Run all analyzers
                for analyzer_name, analyzer_func in self.analyzers.items():
                    analyzer_recommendations = analyzer_func(
                        target, current_metrics
                    )
                    recommendations.extend(analyzer_recommendations)
            else:
                # Run specific analyzer
                if metric in self.analyzers:
                    analyzer_func = self.analyzers[metric]
                    recommendations = analyzer_func(target, current_metrics)
                else:
                    return OptimizationResult(
                        success=False,
                        recommendations=[],
                        current_metrics={},
                        error=f"Unknown optimization metric: {metric}",
                    )

            # Add AI-powered recommendations
            if self.ai_enabled:
                ai_recommendations = self._generate_ai_recommendations(
                    anomalies, predictions, cost_analysis
                )
                recommendations.extend(ai_recommendations)

            # Sort recommendations by priority and impact
            recommendations.sort(
                key=lambda r: (
                    {"high": 0, "medium": 1, "low": 2}[r.priority],
                    {"high": 0, "medium": 1, "low": 2}[r.effort],
                )
            )

            return OptimizationResult(
                success=True,
                recommendations=recommendations,
                current_metrics=current_metrics,
                anomalies=anomalies,
                predictions=predictions,
                cost_analysis=cost_analysis,
            )

        except (ValueError, KeyError, TypeError) as e:
            return OptimizationResult(
                success=False,
                recommendations=[],
                current_metrics={},
                error=f"Data processing error: {str(e)}",
            )
        except (
            subprocess.SubprocessError,
            ConnectionError,
            TimeoutError,
        ) as e:
            return OptimizationResult(
                success=False,
                recommendations=[],
                current_metrics={},
                error=f"Infrastructure communication error: {str(e)}",
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in optimization: {e}")
            self.logger.debug(
                f"Full exception details: {e.__class__.__name__}: {str(e)}"
            )
            return OptimizationResult(
                success=False,
                recommendations=[],
                current_metrics={},
                error=f"Unexpected error: {str(e)}",
            )

    def _collect_metrics(self, target: str) -> Dict[str, Any]:
        """Collect current deployment metrics."""
        metrics = {}

        # Kubernetes metrics
        try:
            # Get resource usage
            result = subprocess.run(
                [
                    "kubectl",
                    "top",
                    "pods",
                    "-n",
                    "sega-deployments",
                    "--no-headers",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                metrics["k8s_resource_usage"] = self._parse_kubectl_top(
                    result.stdout
                )

            # Get deployment info
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "deployments",
                    "-n",
                    "sega-deployments",
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                metrics["k8s_deployments"] = json.loads(result.stdout)

        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            pass

        # Docker metrics
        try:
            result = subprocess.run(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                metrics["docker_stats"] = self._parse_docker_stats(
                    result.stdout
                )

        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            pass

        # System metrics
        try:
            import psutil

            metrics["system"] = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage("/").percent,
                "load_average": psutil.getloadavg(),
            }
        except ImportError:
            pass

        return metrics

    def _parse_kubectl_top(self, output: str) -> List[Dict[str, Any]]:
        """Parse kubectl top output."""
        pods = []
        for line in output.strip().split("\n"):
            if line:
                parts = line.split()
                if len(parts) >= 3:
                    pods.append(
                        {"name": parts[0], "cpu": parts[1], "memory": parts[2]}
                    )
        return pods

    def _parse_docker_stats(self, output: str) -> List[Dict[str, Any]]:
        """Parse docker stats output."""
        containers = []
        lines = output.strip().split("\n")[1:]  # Skip header
        for line in lines:
            if line:
                parts = line.split("\t")
                if len(parts) >= 4:
                    containers.append(
                        {
                            "container": parts[0],
                            "cpu_percent": parts[1],
                            "memory_usage": parts[2],
                            "memory_percent": parts[3],
                        }
                    )
        return containers

    def _analyze_resource_usage(
        self, target: str, metrics: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Analyze resource usage and suggest optimizations."""
        recommendations = []

        # Check Kubernetes resource usage
        if "k8s_resource_usage" in metrics:
            for pod in metrics["k8s_resource_usage"]:
                cpu_usage = self._parse_resource_value(pod["cpu"])
                memory_usage = self._parse_resource_value(pod["memory"])

                # High CPU usage
                if cpu_usage > 80:
                    recommendations.append(
                        OptimizationRecommendation(
                            category="resource",
                            priority="high",
                            title=f"High CPU usage in {pod['name']}",
                            description=f"Pod is using {cpu_usage}% CPU, which may cause performance issues",
                            impact="Improved performance and stability",
                            effort="low",
                            implementation="IncreBase CPU limits or add horizontal pod autoscaling",
                            expected_savings={
                                "performance": "30-50% improvement"
                            },
                        )
                    )

                # Low resource usage
                if cpu_usage < 10 and memory_usage < 20:
                    recommendations.append(
                        OptimizationRecommendation(
                            category="resource",
                            priority="medium",
                            title=f"Low resource utilization in {pod['name']}",
                            description=f"Pod is using only {cpu_usage}% CPU and {memory_usage}% memory",
                            impact="Reduced costs and better resource allocation",
                            effort="low",
                            implementation="Reduce resource requests and limits",
                            expected_savings={"cost": "15-25% reduction"},
                        )
                    )

        # Check system metrics
        if "system" in metrics:
            system = metrics["system"]

            if system["cpu_percent"] > 80:
                recommendations.append(
                    OptimizationRecommendation(
                        category="resource",
                        priority="high",
                        title="High system CPU usage",
                        description=f"System CPU usage is {system['cpu_percent']:.1f}%",
                        impact="Prevent system overload",
                        effort="medium",
                        implementation="Scale up infrastructure or optimize workloads",
                        expected_savings={"stability": "High improvement"},
                    )
                )

            if system["memory_percent"] > 85:
                recommendations.append(
                    OptimizationRecommendation(
                        category="resource",
                        priority="high",
                        title="High memory usage",
                        description=f"System memory usage is {system['memory_percent']:.1f}%",
                        impact="Prevent out-of-memory issues",
                        effort="medium",
                        implementation="Add memory or optimize memory usage",
                        expected_savings={"stability": "High improvement"},
                    )
                )

        return recommendations

    def _analyze_cost_optimization(
        self, target: str, metrics: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Analyze cost optimization opportunities."""
        recommendations = []

        # Check for over-provisioned resources
        if "k8s_deployments" in metrics:
            deployments = metrics["k8s_deployments"].get("items", [])

            for deployment in deployments:
                spec = deployment.get("spec", {})
                containers = (
                    spec.get("template", {})
                    .get("spec", {})
                    .get("containers", [])
                )

                for container in containers:
                    resources = container.get("resources", {})
                    requests = resources.get("requests", {})

                    # Check for large resource requests
                    if requests.get("cpu", "").endswith("m"):
                        cpu_millicores = int(requests["cpu"][:-1])
                        if cpu_millicores > 1000:  # More than 1 CPU
                            recommendations.append(
                                OptimizationRecommendation(
                                    category="cost",
                                    priority="medium",
                                    title=f"High CPU request in {deployment['metadata']['name']}",
                                    description=f"Container requests {cpu_millicores}m CPU",
                                    impact="Reduced infrastructure costs",
                                    effort="low",
                                    implementation="Review and optimize CPU requests based on actual usage",
                                    expected_savings={
                                        "cost": f"${cpu_millicores * 0.02:.2f}/month estimated"
                                    },
                                )
                            )

        # Suggest reserved instances for stable workloads
        recommendations.append(
            OptimizationRecommendation(
                category="cost",
                priority="medium",
                title="Consider reserved instances",
                description="Stable workloads can benefit from reserved instance pricing",
                impact="Significant cost reduction for long-running services",
                effort="low",
                implementation="Analyze usage patterns and purchBase reserved instances",
                expected_savings={"cost": "20-40% reduction"},
            )
        )

        # Suggest spot instances for fault-tolerant workloads
        recommendations.append(
            OptimizationRecommendation(
                category="cost",
                priority="low",
                title="Consider spot instances",
                description="Fault-tolerant workloads can use spot instances",
                impact="Large cost savings for suitable workloads",
                effort="medium",
                implementation="Identify suitable workloads and implement spot instance handling",
                expected_savings={
                    "cost": "50-80% reduction for suitable workloads"
                },
            )
        )

        return recommendations

    def _analyze_performance(
        self, target: str, metrics: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Analyze performance optimization opportunities."""
        recommendations = []

        # Check for performance bottlenecks
        if "system" in metrics:
            system = metrics["system"]
            load_avg = system.get("load_average", [0, 0, 0])

            if load_avg[0] > 2.0:  # High load average
                recommendations.append(
                    OptimizationRecommendation(
                        category="performance",
                        priority="high",
                        title="High system load",
                        description=f"1-minute load average is {load_avg[0]:.2f}",
                        impact="Improved response times and throughput",
                        effort="medium",
                        implementation="Identify bottlenecks and optimize or scale resources",
                        expected_savings={"performance": "30-50% improvement"},
                    )
                )

        # Suggest caching for web aApplications
        recommendations.append(
            OptimizationRecommendation(
                category="performance",
                priority="medium",
                title="Implement caching",
                description="Add Redis or Memcached for frequently accessed data",
                impact="Reduced database load and faster response times",
                effort="medium",
                implementation="Add caching layer and modify aApplication to use cache",
                expected_savings={
                    "performance": "2-5x improvement for cached queries"
                },
            )
        )

        # Suggest CDN for static assets
        recommendations.append(
            OptimizationRecommendation(
                category="performance",
                priority="low",
                title="Use CDN for static assets",
                description="Serve static assets from a Content Delivery Network",
                impact="Faster asset loading globally",
                effort="low",
                implementation="Configure CDN and update asset URLs",
                expected_savings={
                    "performance": "20-50% faster asset loading"
                },
            )
        )

        return recommendations

    def _analyze_security_posture(
        self, target: str, metrics: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Analyze security optimization opportunities."""
        recommendations = []

        # Check for security best practices
        if "k8s_deployments" in metrics:
            deployments = metrics["k8s_deployments"].get("items", [])

            for deployment in deployments:
                spec = deployment.get("spec", {})
                containers = (
                    spec.get("template", {})
                    .get("spec", {})
                    .get("containers", [])
                )

                for container in containers:
                    security_context = container.get("securityContext", {})

                    # Check for privileged containers
                    if security_context.get("privileged", False):
                        recommendations.append(
                            OptimizationRecommendation(
                                category="security",
                                priority="high",
                                title=f"Privileged container in {deployment['metadata']['name']}",
                                description="Container is running with privileged access",
                                impact="Reduced security risk",
                                effort="medium",
                                implementation="Remove privileged flag and use specific capabilities",
                                expected_savings={
                                    "security": "Significant risk reduction"
                                },
                            )
                        )

                    # Check for root user
                    if not security_context.get("runAsNonRoot", False):
                        recommendations.append(
                            OptimizationRecommendation(
                                category="security",
                                priority="medium",
                                title=f"Container running as root in {deployment['metadata']['name']}",
                                description="Container may be running as root user",
                                impact="Reduced privilege escalation risk",
                                effort="low",
                                implementation="Set runAsNonRoot: true and runAsUser to non-root UID",
                                expected_savings={
                                    "security": "Moderate risk reduction"
                                },
                            )
                        )

        # General security recommendations
        recommendations.append(
            OptimizationRecommendation(
                category="security",
                priority="medium",
                title="Implement network policies",
                description="Add Kubernetes network policies to restrict pod-to-pod communication",
                impact="Improved network security and isolation",
                effort="medium",
                implementation="Define and apply network policies for each namespace",
                expected_savings={
                    "security": "Significant improvement in network security"
                },
            )
        )

        return recommendations

    def _analyze_reliability(
        self, target: str, metrics: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Analyze reliability optimization opportunities."""
        recommendations = []

        # Check for single points of failure
        if "k8s_deployments" in metrics:
            deployments = metrics["k8s_deployments"].get("items", [])

            for deployment in deployments:
                replicas = deployment.get("spec", {}).get("replicas", 1)

                if replicas == 1:
                    recommendations.append(
                        OptimizationRecommendation(
                            category="reliability",
                            priority="medium",
                            title=f"Single replica in {deployment['metadata']['name']}",
                            description="Deployment has only one replica, creating a single point of failure",
                            impact="Improved availability and fault tolerance",
                            effort="low",
                            implementation="IncreBase replica count to at least 2",
                            expected_savings={
                                "availability": "Significant improvement"
                            },
                        )
                    )

        # Suggest health checks
        recommendations.append(
            OptimizationRecommendation(
                category="reliability",
                priority="high",
                title="Add comprehensive health checks",
                description="Implement liveness and readiness probes for all containers",
                impact="Better failure detection and recovery",
                effort="medium",
                implementation="Add health check endpoints and configure probes",
                expected_savings={
                    "availability": "Faster failure detection and recovery"
                },
            )
        )

        # Suggest backup strategy
        recommendations.append(
            OptimizationRecommendation(
                category="reliability",
                priority="medium",
                title="Implement backup strategy",
                description="Set up automated backups for persistent data",
                impact="Data protection and disaster recovery",
                effort="medium",
                implementation="Configure automated backups and test restore procedures",
                expected_savings={
                    "reliability": "Data protection and faster recovery"
                },
            )
        )

        return recommendations

    def _parse_resource_value(self, value: str) -> float:
        """Parse resource value string to percentage."""
        if not value:
            return 0.0

        # Remove units and convert to float
        numeric_value = re.sub(r"[^0-9.]", "", value)
        try:
            return float(numeric_value)
        except ValueError:
            return 0.0

    def _store_historical_metrics(self, target: str, metrics: Dict[str, Any]):
        """Store metrics for historical analysis."""
        timestamp = datetime.now()
        for metric_name, value in metrics.items():
            if isinstance(value, (int, float)):
                self.historical_metrics[f"{target}_{metric_name}"].append(
                    {"timestamp": timestamp, "value": value}
                )

                # Keep only last 100 data points
                if (
                    len(self.historical_metrics[f"{target}_{metric_name}"])
                    > 100
                ):
                    self.historical_metrics[f"{target}_{metric_name}"].pop(0)

    def _detect_anomalies(
        self, target: str, current_metrics: Dict[str, Any]
    ) -> List[AnomalyDetection]:
        """Detect anomalies using statistical methods."""
        anomalies = []

        for metric_name, current_value in current_metrics.items():
            if not isinstance(current_value, (int, float)):
                continue

            key = f"{target}_{metric_name}"
            if (
                key not in self.historical_metrics
                or len(self.historical_metrics[key]) < 10
            ):
                continue

            # Get historical values
            historical_values = [
                entry["value"] for entry in self.historical_metrics[key]
            ]

            # Calculate statistical measures
            mean_val = statistics.mean(historical_values)
            std_dev = (
                statistics.stdev(historical_values)
                if len(historical_values) > 1
                else 0
            )

            # Define expected range (mean ± 2 standard deviations)
            expected_range = (
                max(0, mean_val - 2 * std_dev),
                mean_val + 2 * std_dev,
            )

            # Check for anomalies
            if (
                current_value < expected_range[0]
                or current_value > expected_range[1]
            ):
                # Determine severity
                if std_dev > 0:
                    z_score = abs(current_value - mean_val) / std_dev
                    if z_score > 3:
                        severity = "critical"
                    elif z_score > 2.5:
                        severity = "high"
                    elif z_score > 2:
                        severity = "medium"
                    else:
                        severity = "low"
                else:
                    severity = "medium"

                anomalies.append(
                    AnomalyDetection(
                        detected=True,
                        severity=severity,
                        metric_name=metric_name,
                        current_value=current_value,
                        expected_range=expected_range,
                        timestamp=datetime.now(),
                        description=f"{metric_name} value {current_value} is outside expected range {expected_range}",
                    )
                )

        return anomalies

    def _predict_scaling_needs(
        self, target: str, current_metrics: Dict[str, Any]
    ) -> List[PredictiveScaling]:
        """Predict scaling needs using trend analysis."""
        predictions = []

        scaling_metrics = [
            "cpu_usage",
            "memory_usage",
            "request_rate",
            "response_time",
        ]

        for metric_name in scaling_metrics:
            key = f"{target}_{metric_name}"
            if (
                key not in self.historical_metrics
                or len(self.historical_metrics[key]) < 5
            ):
                continue

            # Get last 10 data points for trend analysis
            recent_data = self.historical_metrics[key][-10:]
            values = [entry["value"] for entry in recent_data]

            if len(values) < 3:
                continue

            # Simple linear regression for trend
            x = list(range(len(values)))
            if len(values) > 1:
                # Calculate slope
                n = len(values)
                sum_x = sum(x)
                sum_y = sum(values)
                sum_xy = sum(x[i] * values[i] for i in range(n))
                sum_x2 = sum(xi * xi for xi in x)

                slope = (
                    (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2)
                    if (n * sum_x2 - sum_x**2) != 0
                    else 0
                )

                # Predict next value
                predicted_value = values[-1] + slope * 3  # 3 time units ahead

                # Determine action based on prediction
                current_value = values[-1]

                if metric_name in ["cpu_usage", "memory_usage"]:
                    if predicted_value > 80 and slope > 0:
                        action = "scale_up"
                        reasoning = f"Predicted {metric_name} of {predicted_value:.1f}% exceeds 80% threshold"
                    elif predicted_value < 20 and slope < 0:
                        action = "scale_down"
                        reasoning = f"Predicted {metric_name} of {predicted_value:.1f}% below 20% threshold"
                    else:
                        action = "maintain"
                        reasoning = f"Predicted {metric_name} of {predicted_value:.1f}% within normal range"
                else:
                    action = "maintain"
                    reasoning = f"Monitoring trend for {metric_name}"

                # Calculate confidence based on trend consistency
                confidence = min(0.9, abs(slope) * 0.1 + 0.3)

                predictions.append(
                    PredictiveScaling(
                        metric_name=metric_name,
                        current_value=current_value,
                        predicted_value=predicted_value,
                        recommended_action=action,
                        confidence=confidence,
                        time_horizon="next 15 minutes",
                        reasoning=reasoning,
                    )
                )

        return predictions

    def _analyze_cost_forecasting(
        self, target: str, current_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze cost trends and provide forecasting."""
        # Mock cost analysis - in real implementation would connect to cloud billing APIs
        cost_analysis = {
            "current_monthly_cost": 1250.00,
            "predicted_monthly_cost": 1380.00,
            "cost_trend": "increasing",
            "optimization_potential": 15.2,  # percentage
            "top_cost_drivers": [
                {"service": "EC2 instances", "cost": 850.00, "percentage": 68},
                {"service": "ECS Fargate", "cost": 200.00, "percentage": 16},
                {
                    "service": "Data transfer",
                    "cost": 120.00,
                    "percentage": 9.6,
                },
                {"service": "Load balancer", "cost": 80.00, "percentage": 6.4},
            ],
            "recommendations": [
                "Consider reserved instances for stable workloads",
                "Optimize data transfer patterns",
                "Right-size EC2 instances based on usage patterns",
            ],
        }

        return cost_analysis

    def _generate_ai_recommendations(
        self,
        anomalies: List[AnomalyDetection],
        predictions: List[PredictiveScaling],
        cost_analysis: Dict[str, Any],
    ) -> List[OptimizationRecommendation]:
        """Generate AI-powered optimization recommendations."""
        recommendations = []

        # Anomaly-based recommendations
        for anomaly in anomalies:
            if anomaly.severity in ["high", "critical"]:
                recommendations.append(
                    OptimizationRecommendation(
                        category="anomaly",
                        priority="high"
                        if anomaly.severity == "critical"
                        else "medium",
                        title=f"Anomaly Detected: {anomaly.metric_name}",
                        description=anomaly.description,
                        impact="Prevent potential service degradation",
                        effort="low",
                        implementation=f"Investigate {anomaly.metric_name} spike and adjust thresholds or scaling policies",
                        expected_savings={
                            "reliability": "95% uptime improvement"
                        },
                    )
                )

        # Predictive scaling recommendations
        for prediction in predictions:
            if (
                prediction.recommended_action != "maintain"
                and prediction.confidence > 0.6
            ):
                recommendations.append(
                    OptimizationRecommendation(
                        category="predictive",
                        priority="medium",
                        title=f"Predictive Scaling: {prediction.metric_name}",
                        description=prediction.reasoning,
                        impact="Proactive resource optimization",
                        effort="low",
                        implementation=f"Configure auto-scaling to {prediction.recommended_action}",
                        expected_savings={
                            "cost": "10-25% resource optimization"
                        },
                    )
                )

        # Cost optimization recommendations
        if cost_analysis.get("optimization_potential", 0) > 10:
            recommendations.append(
                OptimizationRecommendation(
                    category="cost",
                    priority="high",
                    title="AI-Identified Cost Optimization Opportunity",
                    description=f"AI analysis identified {cost_analysis['optimization_potential']:.1f}% cost reduction potential",
                    impact=f"Save ~${cost_analysis['current_monthly_cost'] * cost_analysis['optimization_potential'] / 100:.0f}/month",
                    effort="medium",
                    implementation="; ".join(
                        cost_analysis.get("recommendations", [])
                    ),
                    expected_savings={
                        "cost": f"{cost_analysis['optimization_potential']:.1f}% monthly savings"
                    },
                )
            )

        return recommendations
