const data =
{
  "languages": [
    {
      "value": "en-US",
      "name": "English (United States)",
      "prompt_name": "English",
      "hello": "Hello, Soit!"
    },
    {
      "value": "zh-CN",
      "name": "简体中文",
      "prompt_name": "Chinese Simplified",
      "hello": "你好，Soit！"
    }
  ]
}

export const languages = data.languages

export const LanguagesArr = data.languages.map(item => item.value)
