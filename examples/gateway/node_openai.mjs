// Call SOIT's OpenAI-compatible gateway with the OpenAI Node SDK.
//
//   npm install openai
//   export SOIT_BASE_URL=http://localhost:9200/v1
//   export SOIT_API_KEY=sk_...                    # Settings > API
//   export SOIT_MODEL=model:openai-main:gpt-5.5   # from GET /v1/models
//   node node_openai.mjs
import OpenAI from 'openai'

const client = new OpenAI({
  baseURL: process.env.SOIT_BASE_URL ?? 'http://localhost:9200/v1',
  apiKey: process.env.SOIT_API_KEY,
})
const model = process.env.SOIT_MODEL

const models = []
for await (const item of client.models.list()) models.push(item.id)
console.log('models:', models)

// Every call is a governed run; the raw response carries its id.
const { data: completion, response } = await client.chat.completions
  .create({ model, messages: [{ role: 'user', content: 'Say hello in five words.' }] })
  .withResponse()
console.log('run:', response.headers.get('x-soit-run-id'))
console.log('reply:', completion.choices[0].message.content)

const stream = await client.chat.completions.create({
  model,
  messages: [{ role: 'user', content: 'Count to five.' }],
  stream: true,
  stream_options: { include_usage: true },
})
for await (const chunk of stream) {
  const text = chunk.choices[0]?.delta?.content
  if (text) process.stdout.write(text)
  if (chunk.usage) console.log(`\ntokens: ${chunk.usage.total_tokens}`)
}

// An embedding model has its own ref, e.g. model:openai-main:text-embedding-3-small.
if (process.env.SOIT_EMBEDDING_MODEL) {
  const embedding = await client.embeddings.create({
    model: process.env.SOIT_EMBEDDING_MODEL,
    input: 'governed agents',
  })
  console.log('embedding dimensions:', embedding.data[0].embedding.length)
}
