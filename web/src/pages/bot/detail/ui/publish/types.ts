export interface Version {
  version: string;
  date: string;
  author: string;
  status: string;
  description: string;
  changes?: string;
  deployments?: number;
}

export interface Deployment {
  id?: string;
  environment?: string;
  name?: string;
  status: string;
  version: string;
  lastDeployed: string;
  url: string;
  traffic?: string;
}
