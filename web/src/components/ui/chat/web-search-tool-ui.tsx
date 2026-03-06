import { makeAssistantToolUI } from "@assistant-ui/react";
 
type WebSearchArgs = {
  query: string;
};
 
type WebSearchResult = {
  title: string;
  description: string;
  url: string;
};
 
export const WebSearchToolUI = makeAssistantToolUI<
  WebSearchArgs,
  WebSearchResult
>({
  toolName: "web_search",
  render: ({ args, status }) => {
    return <p>web_search({args.query})</p>;
  },
});