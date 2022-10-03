import re
import json
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

class App:
    def __init__(self, driverPath, load=False, debug=False, startPage = 1):
        self.receipeUrl = "https://www.10000recipe.com/recipe/list.html"
        self.driver = webdriver.Chrome(driverPath)
        self.currentReceipePage = startPage - 1
        self.ingredientDict = {'count': 0}
        self.receipeDict = {}
        self.tempReceipeDict = {}
        self.diffFormatList = []
        self.saveDirectory = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'results')
        self.startTime = ''

        self.debug = debug

        if load is True:
            self.receipeDict = self.loadJson('receipe.json')
            self.tempReceipeDict = self.loadJson('temp.json')
            self.ingredientDict = self.loadJson('ingredient.json')
            self.diffFormatList = self.loadJson('diff_format.json')

    def run(self):
        self.startTime = datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss")

        directory = createFolder(os.path.join(self.saveDirectory, self.startTime))
        if directory is None:
            print("디렉토리 생성 실패로 인해 프로그램을 종료합니다.")
            return

        # 불러온 파일 새로 저장
        self.saveJson('receipe.json', self.receipeDict)
        self.saveJson('temp.json', self.tempReceipeDict)
        self.saveJson('ingredient.json', self.ingredientDict)
        self.saveJson('diff_format.json', self.diffFormatList)
            
        # receipeFilePath = os.path.join(directory, "/receipe.json")
        # tempReceipeFilePath = os.path.join(directory, "/temp.json")
        # ingredientFilePath = os.path.join(directory, "/ingredient.json")
        
        while True:
            self.nextReceipePage()
            try:
                self.driver.find_element(By.CSS_SELECTOR, '#contents_area_full > ul > div.result_none')    
                break
            except:
                pass

            receipeElementList = self.getReceipeListFromCurrentPage()
            for receipeElement in receipeElementList:
                receipe = self.getReceipe(receipeElement)
                if receipe is None:
                    continue

                title = receipe['title']

                if self.isTempType(receipe) == True:
                    self.tempReceipeDict[title] = receipe
                else:
                    self.receipeDict[title] = receipe

                # save
                self.saveJson('receipe.json', self.receipeDict)
                self.saveJson('temp.json', self.tempReceipeDict)
                self.saveJson('ingredient.json', self.ingredientDict)
        

    def getReceipe(self, receipeElement):
        result = {}

        # open new tab
        temp = receipeElement.find_element(By.XPATH, './div[1]/a')
        url = temp.get_attribute('href')

        # get title
        title = receipeElement.find_element(By.CSS_SELECTOR, 'div.common_sp_caption_tit').text
        if (title in self.receipeDict) or (url in self.diffFormatList) or (title in self.tempReceipeDict):
            print("이미 크롤링한 레시피이므로 패스")
            return None

        temp.send_keys(Keys.CONTROL + "\n")
        self.driver.switch_to.window(self.driver.window_handles[1])

        try:
            receipeSteps = self.driver.find_elements(By.CSS_SELECTOR, 'div.view_step_cont')
            ingredientContainer = self.driver.find_element(By.XPATH, '//*[@id="divConfirmedMaterialArea"]')
        except:
            print("포맷이 다르므로 패스")
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])

            # 다른 포맷 url 저장
            if url not in self.diffFormatList:
                self.diffFormatList.append(url)
                self.saveJson('diff_format.json', self.diffFormatList)

            return None

        result['title'] = title
        result['url'] = url
        result['image'] = self.driver.find_element(By.XPATH, '//*[@id="main_thumbs"]').get_attribute('src')

        if self.debug is True:
            print('레시피 제목 : ' + result['title'])

        # get step
        result['step'] = []
        receipeSteps = self.driver.find_elements(By.CSS_SELECTOR, 'div.view_step_cont')
        for receipeStep in receipeSteps:
            temp = []
            content = receipeStep.find_element(By.CSS_SELECTOR, 'div.media-body').text
            temp.append(content)
            imgs = receipeStep.find_elements(By.CSS_SELECTOR, 'div.media-right img')
            for img in imgs:
                temp.append(img.get_attribute('src'))
            result['step'].append(temp)
            
            if self.debug is True:
                print(temp, end='\n\n')

        # get ingredient
        result['ingredient'] = self.getIngredient(ingredientContainer)

        # close tab
        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[0])
        return result

    def getIngredient(self, element):
        # get ingredient
        result = []
        ingredientList = element.find_elements(By.TAG_NAME, 'ul')
        
        if self.debug is True:
            print('재료 >>')

        for i in ingredientList:
            subtitleElement = i.find_element(By.TAG_NAME, 'b')
            subtitle = re.sub('[\[\]]', '', subtitleElement.text)

            if self.debug is True:
                print('\t재료 그룹 : ' + subtitle)


            subList = i.find_elements(By.TAG_NAME, 'li')
            for j in subList:
                try:
                    ingreDientElement = j.find_element(By.TAG_NAME, 'a')
                    # 재료 상세 정보 저장
                    ingredientDetail = self.getIngredientDetail(ingreDientElement)
                    name = ingredientDetail['name']
                    self.ingredientDict[name] = ingredientDetail

                    ingredient = ingreDientElement.text

                    unit = j.find_element(By.TAG_NAME, 'span').text
                    result.append({
                        'id': ingredientDetail['id'],
                        'name': ingredient.replace('\n', ''),
                        'unit': unit
                    })

                except:
                    ingredient = j.text
                    unit = j.find_element(By.TAG_NAME, 'span').text
                    result.append({
                        'id': -1,
                        'name': ingredient.replace(unit, '').replace('\n', ''),
                        'unit': unit
                    })

                if self.debug is True:
                    print('\t\t' + ingredient, unit, end='\n\n')

        return result

    def getIngredientDetail(self, element):
        result = {}
        # element.click()
        element.send_keys(Keys.ENTER)

        modal = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, '//*[@id="materialViewModal"]'))
        )

        # get name
        try:
            result['name'] = modal.find_element(By.XPATH, '//*[@id="materialBody"]/div/div[1]/div[2]/b').text
        except: 
            result['name'] = modal.find_element(By.XPATH, '//*[@id="materialBody"]/div/div[1]/div/b').text

        if self.debug is True:
            print('\t\t재료 이름 : ' + result['name'])


        if result['name'] in self.ingredientDict:
            temp = self.ingredientDict[result['name']].copy()
            temp['name'] = result['name']
            
            # close modal    
            modal.find_element(By.XPATH, '//*[@id="materialViewModal"]/div/div/div[1]/button').click()
            
            WebDriverWait(self.driver, 20).until(
                EC.invisibility_of_element_located((By.XPATH, '//*[@id="materialViewModal"]'))
            )
            return temp

        self.ingredientDict['count'] += 1
        result['id'] = self.ingredientDict['count']

        # get image
        try:
            imageElement = modal.find_element(By.XPATH, '//*[@id="materialBody"]/div/div[1]/div[1][@class="ingredient_pic"]')
            imageUrl = re.split('[()]', imageElement.value_of_css_property('background-image'))[1]
            result['image'] = imageUrl.replace('"', '')
        except:
            result['image'] = ''

        # get info
        if self.debug is True:
            print('\t\t재료 정보 >>')

        result['info'] = {}
        infos = modal.find_elements(By.XPATH, '//*[@id="materialBody"]/div/div[2]/table/tbody/tr')
        for info in infos:
            title = info.find_element(By.TAG_NAME, 'th').text
            value = info.find_element(By.TAG_NAME, 'td').text
            result['info'][title] = value

            if self.debug is True:
                print('\t\t\t' + title + " : " + value)

        # get efficacy (효능)
        if self.debug is True:
            print('\t\t효능 >>')
        result['efficacy'] = []
        try:
            efficacys = modal.find_elements(By.XPATH, '//*[@id="materialBody"]/div/dl[1]/dd/div/a')
            for efficacy in efficacys:
                result['efficacy'].append(efficacy.text)
                if self.debug is True:
                    print('\t\t\t' + efficacy.text)
        except:
            pass

        # close modal    
        modal.find_element(By.XPATH, '//*[@id="materialViewModal"]/div/div/div[1]/button').click()
        
        WebDriverWait(self.driver, 20).until(
            EC.invisibility_of_element_located((By.XPATH, '//*[@id="materialViewModal"]'))
        )

        return result

    def isTempType(self, receipe):
        for ingredient in receipe['ingredient']:
            if ingredient['id'] == -1:
                return True
        return False

    
    def goReceipePage(self, page: int):
        self.driver.get("%s?order=date&page=%d" % (self.receipeUrl, page))
        
    def nextReceipePage(self):
        self.currentReceipePage += 1
        self.goReceipePage(self.currentReceipePage)

    def prevReceipePage(self):
        if self.currentReceipePage > 1:
            self.currentReceipePage -= 1
        self.goReceipePage(self.currentReceipePage)

    def getReceipeListFromCurrentPage(self):
        receipeListContainer = self.driver.find_element(By.XPATH, '//*[@id="contents_area_full"]/ul/ul')
        return receipeListContainer.find_elements(By.TAG_NAME, 'li')

    def saveJson(self, filename, content):
        with open(os.path.join(self.saveDirectory, self.startTime, filename), 'w', encoding='utf8') as jsonFile:
            json.dump(content, jsonFile, indent="\t", ensure_ascii=False)

    def loadJson(self, filename):
        last_directory = os.listdir(self.saveDirectory)[-1]
        with open(os.path.join(self.saveDirectory, last_directory, filename), 'r', encoding='utf8') as f:
            return json.load(f)

def createFolder(path):
    import os

    try:
        if not os.path.exists(path):
            os.makedirs(path)
        return path
    except OSError:
        print('Error: Creating directory. ' + path)
        return None