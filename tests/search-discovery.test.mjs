import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import worker from '../src/index.js';

const origin = 'https://statementiq-lb.com';
const read = path => readFileSync(new URL('../static/' + path, import.meta.url), 'utf8');
const sitemap = read('sitemap.xml');
const urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match => match[1]);
const assetPath = path => path === '/' ? 'index.html' : path.slice(1) + '.html';

test('every sitemap page has unique metadata, a matching canonical and valid structured data', () => {
    const titles = new Set();
    for (const url of urls) {
        const html = read(assetPath(new URL(url).pathname));
        assert.ok(html.includes(`<link rel="canonical" href="${url}">`), url);
        const title = html.match(/<title>([^<]+)<\/title>/)[1];
        assert.ok(!titles.has(title), 'Titles must distinguish pages');
        titles.add(title);
        assert.match(html, /<meta name="description" content="[^"\n]{50,200}">/);
        assert.match(html, /<meta name="robots" content="index, follow/);
        assert.match(html, /<html lang="en"/);
        for (const block of html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)) {
            const data = JSON.parse(block[1]);
            assert.equal(data['@context'], 'https://schema.org');
            assert.ok(data['@graph'].some(item => item.url === url));
        }
    }
});

test('public pages are reachable through normal links and their local assets exist', () => {
    const home = read('index.html');
    for (const url of urls.filter(url => url !== origin + '/')) {
        const path = new URL(url).pathname;
        assert.ok(home.includes(`href="${path}"`), path + ' needs a homepage link');
        const html = read(assetPath(path));
        assert.equal((html.match(/<h1[\s>]/g) || []).length, 1);
        for (const match of html.matchAll(/(?:href|src)="(\/(?!\/)[^"#]*)"/g)) {
            const linked = new URL(match[1], origin).pathname;
            const file = linked.startsWith('/static/') ? linked.slice(8) : linked.slice(1);
            assert.ok(linked === '/' || existsSync(new URL('../static/' + file, import.meta.url)) || existsSync(new URL('../static/' + file + '.html', import.meta.url)), linked);
        }
        assert.ok(!html.includes('request-client.js') && !html.includes('app.js') && !html.includes('plotly-'), 'Public pages must not start analysis or load charts');
    }
});

test('public content is served through assets without contacting the analysis backend', async () => {
    for (const url of urls) {
        const response = await worker.fetch(new Request(url), {ASSETS: {fetch: async request => {
            assert.equal(request.url, url);
            return new Response(read(assetPath(new URL(url).pathname)), {headers: {'content-type': 'text/html'}});
        }}}, {});
        assert.equal(response.status, 200);
        assert.equal(response.headers.get('x-robots-tag'), null);
    }
    const redirect = await worker.fetch(new Request(origin + '/static/index.html?ref=old'), {}, {});
    assert.equal(redirect.status, 301);
    assert.equal(redirect.headers.get('location'), origin + '/?ref=old');
    const missing = await worker.fetch(new Request(origin + '/missing'), {ASSETS: {fetch: async () => new Response(read('404.html'), {status: 404})}}, {});
    assert.equal(missing.status, 404);
    assert.match(await missing.text(), /noindex, follow/);
    assert.equal(JSON.parse(readFileSync(new URL('../wrangler.jsonc', import.meta.url), 'utf8')).assets.not_found_handling, '404-page');
});

test('public theme controls still work when browser storage is unavailable', () => {
    const listeners = {};
    const attributes = {};
    const toggle = {setAttribute: (key,value) => {attributes[key] = value;}, addEventListener: (key,fn) => {listeners[key] = fn;}};
    const context = vm.createContext({
        document: {documentElement: {setAttribute: (key,value) => {attributes[key] = value;}}, querySelector: () => toggle, querySelectorAll: () => [], addEventListener: (key,fn) => {listeners[key] = fn;}},
        window: {location: {pathname: '/about'}},
        localStorage: {getItem() {throw Error('Blocked');}, setItem() {throw Error('Blocked');}},
    });
    vm.runInContext(read('public-pages.js'), context);
    listeners.DOMContentLoaded();
    assert.equal(attributes['data-theme'], 'light');
    listeners.click();
    assert.equal(attributes['data-theme'], 'dark');
    assert.equal(attributes['aria-label'], 'Switch to light mode');
});
