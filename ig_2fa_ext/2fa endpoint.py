import requests

url = "https://accountscenter.instagram.com/api/graphql/"

payload = {
  'av': "17841425099493719",
  '__user': "0",
  '__a': "1",
  '__req': "x",
  '__hs': "20731.HYP:accounts_center_pkg.2.1...0",
  'dpr': "3",
  '__ccg': "EXCELLENT",
  '__rev': "1049282529",
  '__s': "63h6du:dl5z7n:ctnkzy",
  '__hsi': "7693116928203452176",
  '__dyn': "7xe5Wxa13xu1syU8EKmhe3a2q1DxiFGxK7oG1-zEdF8iBxa361MwFwJzUS8xe1Bw8i7oqx611wno2wgaU7i2qq1eCyUhxR162-8G6kE8Ro4uUfo2lxF122y5oeEjz98eUa8465UScw9a0CE4a4o4a786a6oowv89k2CcAwOwAwgk6U-3K5E7VxK48W7p8hAwGK2efK1YwCxe68hzE2Zwzzo5G4E5y58Twn9U4S1pxi9hobE7m1LxW4oO3B2oS2e1jwVwkQuawaG15wFBwNwNAyo884K6o9EbrxS9wr8aEbAeg5qiu2mcwHwzK0zouzpo4d0ea6o467ofo6y10zU9oam4EO6E4S1awoUCu685mEdUf8nKUly-19wzzQ",
  '__csr': "gkNQQA9hf5bsD49n54f9bliFNY9LduSLuBORRCFqp2Oa8DBZHB_tqn8J9_O5FZqml4yumPvn5lha8GAKFqTGi_JTqWjAFb-XiHSYAGWBZCH9aihJajWOQFAQP7AAz9VbzaGVQ9CHBWl4VfFd2eAEHAh98JfmFdfbyukFpamiAimuilDQdylAAQaAyp-Hhf-iBghKu_ybAK6ES5URDBBy8Khrvy8CqquEXKi4bU_DVXAzKVEB3V8C14iml2F2zK-q9jyeGV-KGO6XipA8GoWht69BgB94F4qhyUFp6z_8mJoOHhFQGl6BfL_z8JVqLxt6CBCDAhkFnJqpuO2pXyqo6C8glATmFHFkby99UGuhfACz8y4vvD4l43miGlyfviiy5yya4448K9lvVR-yN2xaESiYMgNxkxkJbWj412HjGXO1nR4h0ijwdO7876czrVFbina49EbQeK5C26cKq3vgoxK2ayxi2ei8EAaby8BaQAIxAvy5ytrgkGqlwVLy9Uk8m8kj5afxmh0J2UKt3prxz8BwirAyUB0Ly8jK1-wlERep7wAx675K5f-6p-13wyHFKamMDG9-9Q5ErgtHK8wRCo4i8zA3mJ05iAUixqsE3EwBxh1ObmGL5k6d1x0AzumRjBmqlxOjBgXFyoCih2qDaCOoyU7-6EsyE6C2O1twPyUsAcJqoR1F5GZ1ihrgTUy6kaU46h6ZoW9wdq4rxP5ixaE3ywHxHa0a70q0uLgeKk6QV990UwPP25A1FtigyXjKnV9bymPWb8Si-RIp8Fohy9ZppfeiaEp5e9iQEtEt48vliGinAEokWk9cCMD6mN1bJ8ih2owIiTBbsIhX9YGaKhp4HhPBaB26hB2Msc4EckG8By2FGLDNkrkKExWxGXwgUK1tMs85X4hiUNC1OBagGW7agoIxTmti83ow3hUBhixtgpa1C0qgibjVUOF3F3kqcCCGF58hDAmFUG-9gH0gzcAw80mErCnD8Amu548zaVAh5h8gj89LB8A9Zd5Gp2b3Ib18VKmjalPdGquWeAEgGmXGbhogxlqxKFZQbojyEOSmFB3s8ekeymBOx2bhjhoKNaM6Aexd1VU8syAyYpHy46Xx8ctmib1H1Hh9b0jknN94Qws9HQbiahCuxwF8FkV4N24IzyUyUHynCKior4QlcF9ash5q8jhAsEGp924bG4rojAk1EQDDpJcHOAyVyloVaMqg3H0FwRwuE6a0h60nnodEy0oW0OE3Mwzwbu5oKiEGC4FE4lVoF3o4nw5YwhE6KqUvU9FBxy0yoNxq84AGaw0ORwglu0uqdyu2q4qwc_CgO5Cl7yd6glCCgbU5u1fBw8W_RpVe2Dxm2Cq9G7JU_CVUy22dxbD9G6Eyayp20HwhA0a6KaWGfWFoHj8wPDUgc8wLDHUngC2ucyp8CrXnDHxXjKqleh7wjA1GKbgphV3hh8Gm3Kbch29Qm5ouwQEyw5dwDwp9u4oR0gU884S0FEiyV8kw4EBbswvBixQE3nwMy8Gewjodyx68wCwgeac0qi0kC1Pwz5oGegfqxlo_g8o4PXLGeHwIzEXc2S6874U5G9wc65uMxzEaEixmn4R815xu6py04gJ024-3tah5xy6ECdyUK6E4a26bzEG14ByUOmUcV3169y41MxC8w4UwioHa1CxW5E8E2qw9vBAw6hw8Z1lwHYU7Jw-g5P38KNca8d3uGg4FCG2i1U5cpoC1ygaoqwwgo50go6i9X80mn53VC460h86goei9lgciw9Ou290cG8AwA372E4q0rmi4olABAAyF8yUtGUbUhwwgy1ezrBzoR2VpE0SS1NwCorxG1Mzo7YM7e2d0sUbUSfwvF8Ci8yp94VHAKWzoCV998-iquiiuq408y3-S5DGAu2N90zwg46yxgMBGNwkKmiqii2m2q2h6VQmiVp9qAVE8A58DDgOi1lwo998gxq14xe3edDKqFUlypVbGFpbx128nUW9ByoBDDzAt0FzE5e1PxRAwk9kV8K2eiii9wHwtpk045EiwmGxW260qg3B52Vx1G68b90psgEFgI1YgswoBeJ272OwM0Owg8K1TodU0BO1AysEB1s22se0OjqllCHeOQ8oeE2Vy5o7m2OhCiwVpflIB8maDpUG58C0Ll49yl2OwMkd70wwS8VpUTVE3Ew4gwR84820y88Ud86KqewiEKbQgn8u4Hxh3oWqGKjFagFaEF5gy54gEgByi0lo7e28cAnNGrAfiNhk2icxJ7oRA38K891d4amXai5k7Elklsc8VCibgG-s6tb5A3ogG0Fo3qg1HF3iAwTeVj2S8q2JdcCAh0cQ1BEaApttlF89jbaTM82Nk3U4SF99pcD0v08o2ax28geF9pedQ1KxFx-L-6G1zyt2K2Bw9l08caMO6-5UpBXw8i741So56dDwIcu1Vwam2fyp9oS9VVp9eqewv8eo5u5US54iHjEw33GoL6935i81EeMNffhlBntAGCpjtihqi2bX68t8UyA1ta48eQ0LUjwiO1O15oqo6hCsA9N54xqxbam4Eb8c4fa36262m0B0EB1OzJgd05r4Ibl2M98GR38mk62J7ACGiml0Q0phEZ2petcI94hVyk36310poqqo4e0OHCG3K5UhDxy69E",
  '__hsdp': "gtMpgpI1Lky8q9DP8UEgh5VUB1qy281wg3h3GOy0yswxGkO4DHl0aF4w6UGb4zO16kpgScAyIgfy5yyPxkQyAa7F_L42hrh-8eWaoP0pb2yh65k1ohE8InFwYU4UYw6u3cm2WcyQ2-b868yaz827ho0Ho4-8xl0E5zWwhoK3EUG2EMqw9h4wegi2K1ogszNg8awIg34hC08sg5l2S0yS5U8A585O0MUjw4jg4G0BE2lxq3eK0j22O0FU6-cwsU13EDxO0n6ewlU0VO0KUe8iw6swr-Wy80r-wlUMJ1CawAwKw9yU3mw7GVQawEiw5Jw5rwQwrU2rg1GoK0NU2bDABgvK11wbCK1eBBy9o2ew96dx-i1Fwgo7i4U28w5tyXwi87eU1xErw9204xE1Tk1Gw9i0T40-k5EcAfz6HAyomymcgvCwjool0BzE",
  '__hblp': "1q0lS580Y6ewDxm9U0C-Hx62e2yucykdyEB3o8ojx2Ex167uEa82pyUe87G3q2221wq8yfw_U8E4u5Uc4p1-p2V8623m0K80ym8z8y6UC7KiUd9UBwKx6aK7oy7U623C3e6Eoxe1CwRwOwg-cwKUkwgFos-5QpwjEOq2KSq0ui58fQm9w-wHCAx-5mdxqeyo9o3RwByokzk3O1jwjob8R121txamdxm9Gm5UcUhwAwbW13xW8wNwIwQwsEgBU4i7E7e15wj87K9zogwmo1iE3gwajzVEty8V1a589omwg84ei3emaDgOU5uEG1Jyo5qm8Utxi2aUa8CuEfGyErgboC5EK1by410xmm2i6pEdovwUgc8uw2080Zm2B0Cxt7xy8Gh0a-260wFUiBwwwUwQBxe4o6WbxZ0kE25Dxmu26VUGdz8lVQ6byogCwzo6CaABo98lwrony8kzawByV8K7t12HzQexNa2m29124UkwLG6UqwBG7EtwEAy8vBwxwlm2i2WeAx-0FXwDCwGz8igcU88jxm68sBDAgngF6wMosJ0IwEwjo-5F8FwzU8oTgcp8nAwVAzpErgC12DBx55K6omxO4Uak4EgwDigcUbo-4Ey1iK15gsz9EdE6euq7ElxS2nCwAyEghEe8uwn84y0hO10y44pE2Uxe8xa483oDUb8rAwkEK08dyo2gxWU20hU9EGfwywJwsolxO3a4A4VUbU6CewfW0DEeHG5Ey19K65g8U",
  '__sjsp': "grT1B1CM4h0wMDKl2ECvczyx14nDyk5Gm8w610d44sEAsagWmfDAl02qo9y0Pz8clwaOWaoN06g3t0m4q2a460uy",
  '__comet_req': "24",
  'fb_dtsg': "NAfzZYGlH0vsuo8H5VLFSRTqqnuT90SfeRXYgjNXo5zV2LfBT2lEYxg:17843671327157124:1791193230",
  'jazoest': "26336",
  'lsd': "Acn9EC1a_aWYWb9iJeKopf",
  '__spin_r': "1049282529",
  '__spin_b': "trunk",
  '__spin_t': "1791193366",
  '__crn': "comet.fx.accounts_center.security.two_factor",
  'qpl_active_flow_ids': "241970459",
  'fb_api_caller_class': "RelayModern",
  'fb_api_req_friendly_name': "useFXSettingsTwoFactorGenerateTOTPKeyMutation",
  'server_timestamps': "true",
  'variables': "{\"input\":{\"actor_id\":\"17841425099493719\",\"client_mutation_id\":\"f5579220-e24e-4ab8-a924-ee38fe18f57f\",\"account_id\":\"17841425099493719\",\"account_type\":\"INSTAGRAM\",\"device_id\":\"device_id_fetch_ig_did\",\"fdid\":\"device_id_fetch_ig_did\"}}",
  'doc_id': "9837172312995248",
  'fb_api_analytics_tags': "[\"qpl_active_flow_ids=241970459\"]"
}

headers = {
  'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Mobile Safari/537.36",
  'Accept-Encoding': "gzip, deflate, br, zstd",
  'sec-ch-ua-full-version-list': "\"Chromium\";v=\"154.0.8037.94\", \"Google Chrome\";v=\"154.0.8037.94\", \"Not A(Brand\";v=\"99.0.0.0\"",
  'sec-ch-ua-platform': "\"Android\"",
  'x-fb-upl-sessionid': "upl_1791193371880_4ca5e66a-fada-47c2-88e5-af1cb65a2bf8",
  'x-bh-flowsessionid': "upl_wizard_1791193371880_bb6a8fef-3e79-4f00-a238-62cb91c7da65",
  'sec-ch-ua': "\"Chromium\";v=\"154\", \"Google Chrome\";v=\"154\", \"Not A(Brand\";v=\"99\"",
  'sec-ch-ua-model': "\"V2338\"",
  'sec-ch-ua-mobile': "?1",
  'x-ig-app-id': "1217981644879628",
  'x-fb-lsd': "Acn9EC1a_aWYWb9iJeKopf",
  'x-fb-friendly-name': "useFXSettingsTwoFactorGenerateTOTPKeyMutation",
  'x-asbd-id': "359341",
  'sec-ch-prefers-color-scheme': "light",
  'dnt': "1",
  'x-fb-upl-sessionid-shadow': "upl_1791193371880_4ca5e66a-fada-47c2-88e5-af1cb65a2bf8",
  'sec-ch-ua-platform-version': "\"16.0.0\"",
  'origin': "https://accountscenter.instagram.com",
  'sec-fetch-site': "same-origin",
  'sec-fetch-mode': "cors",
  'sec-fetch-dest': "empty",
  'referer': "https://accountscenter.instagram.com/password_and_security/two_factor/",
  'accept-language': "en-GB,en-US;q=0.9,en;q=0.8",
  'priority': "u=1, i",
  'Cookie': "ig_did=9D44A7E2-E727-4CB1-95C6-A9918B02608E; datr=F3DDatpnWD5ezPFPKoQpDc_f; wd=436x878; dpr=2.4750001430511475; mid=asNwGAABAAFHNk2-j-4DXoR8042k; ps_l=1; ps_n=1; csrftoken=IiVPDpmer8uKwtwHmPkC6N4ByAch6DiB; ds_user_id=25149756649; sessionid=25149756649%3ADTN3ztqsaze9b0%3A2%3AAYmSX3yKKPabDy7awvTYwqTOZNfRF-KLDH0LIUXc9g; rur=DKL%2C17841425099493719%2C1792402982%3A01ff5234191f23e997f2388f43015f68f1c4ee7c59fc70616c6c4c3261bf7a6929404491"
}

response = requests.post(url, data=payload, headers=headers)

print(response.text)