export interface HealthStatus {
  status: string;
  database: string;
  redis: string;
}

export interface MetricCardData {
  title: string;
  value: number | string;
  subtext: string;
  type: 'total' | 'healthy' | 'changed' | 'errors';
}
