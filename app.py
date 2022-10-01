from inspect import trace
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
    def __init__(self, driverPath, load=False, debug=False):
        self.receipeUrl = "https://www.10000recipe.com/recipe/list.html"
        self.driver = webdriver.Chrome(driverPath)
        self.currentReceipePage = 0
        self.ingredientDict = {'count': 0}
        self.receipeDict = {}
        self.diffFormatList = []
        self.saveDirectory = './results'
        self.startTime = ''

        self.debug = debug

        if load is True:
            self.loadReceipeDict(self.saveDirectory)
            self.loadIngredientDict(self.saveDirectory)
            self.loadDiffFormatList(self.saveDirectory)

    def run(self):
        directory = createFolder(self.saveDirectory)
        if directory is None:
            print("디렉토리 생성 실패로 인해 프로그램을 종료합니다.")
            return

        self.startTime = datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss")
        receipeFilePath = directory + "/receipe_" + self.startTime + ".json"
        ingredientFilePath = directory + "/ingredient_" + self.startTime + ".json"
        
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
                del receipe['title']
                self.receipeDict[title] = receipe

                # save
                self.saveReceipeDict(receipeFilePath)
                self.saveIngredientDict(ingredientFilePath)

        

    def getReceipe(self, receipeElement):
        result = {}

        # open new tab
        temp = receipeElement.find_element(By.XPATH, './div[1]/a')
        url = temp.get_attribute('href')

        # get title
        title = receipeElement.find_element(By.CSS_SELECTOR, 'div.common_sp_caption_tit').text
        if (title in self.receipeDict) or (url in self.diffFormatList):
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
                diffFormatFilePath = self.saveDirectory + "/diff_format_" + self.startTime + ".json"
                self.saveDiffFormatList(diffFormatFilePath)

            return None

        result['title'] = title
        # result['url'] = self.driver.current_url
        result['url'] = url

        if self.debug is True:
            print('레시피 제목 : ' + result['title'])

        # get step
        result['step'] = []
        receipeSteps = self.driver.find_elements(By.CSS_SELECTOR, 'div.view_step_cont')
        for receipeStep in receipeSteps:
            content = receipeStep.find_element(By.CSS_SELECTOR, 'div.media-body').text
            imgUrl = receipeStep.find_element(By.CSS_SELECTOR, 'div.media-right > img').get_attribute('src')
            result['step'].append([content, imgUrl])

            if self.debug is True:
                print(content, imgUrl, end='\n\n')

        # get ingredient
        result['ingredient'] = self.getIngredient(ingredientContainer)

        # close tab
        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[0])
        return result

    def getIngredient(self, element):
        # get ingredient
        result = {}
        ingredientList = element.find_elements(By.TAG_NAME, 'ul')
        
        if self.debug is True:
            print('재료 >>')

        for i in ingredientList:
            subtitleElement = i.find_element(By.TAG_NAME, 'b')
            subtitle = re.sub('[\[\]]', '', subtitleElement.text)

            if self.debug is True:
                print('\t재료 그룹 : ' + subtitle)

            result[subtitle] = []

            subList = i.find_elements(By.TAG_NAME, 'li')
            for j in subList:
                try:
                    ingreDientElement = j.find_element(By.TAG_NAME, 'a')
                    # 재료 상세 정보 저장
                    ingredientDetail = self.getIngredientDetail(ingreDientElement)
                    name = ingredientDetail['name']
                    del ingredientDetail['name']
                    self.ingredientDict[name] = ingredientDetail

                    ingredient = ingreDientElement.text

                    unit = j.find_element(By.TAG_NAME, 'span').text
                    result[subtitle].append({
                        'id': ingredientDetail['id'],
                        'name': ingredient,
                        'unit': unit
                    })

                except:
                    ingredient = j.text
                    unit = j.find_element(By.TAG_NAME, 'span').text
                    result[subtitle].append({
                        'id': -1,
                        'name': ingredient.replace(unit, ''),
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

    def saveReceipeDict(self, filePath):
        with open(filePath, 'w', encoding='utf8') as jsonFile:
            json.dump(self.receipeDict, jsonFile, indent="\t", ensure_ascii=False)

    def loadReceipeDict(self, saveDirectory):
        file_list = os.listdir(saveDirectory)
        file_list_receipe = [file for file in file_list if file.startswith("receipe")]
        last_receipe_file = file_list_receipe[-1]
        
        with open(saveDirectory + "/" + last_receipe_file, 'r', encoding='utf8') as f:
            self.receipeDict = json.load(f)
            
    def saveIngredientDict(self, filePath):
        with open(filePath, 'w', encoding='utf8') as jsonFile:
            json.dump(self.ingredientDict, jsonFile, indent="\t", ensure_ascii=False)

    def loadIngredientDict(self, saveDirectory):
        file_list = os.listdir(saveDirectory)
        file_list_ingredient = [file for file in file_list if file.startswith("ingredient")]
        last_ingredient_file = file_list_ingredient[-1]

        with open(saveDirectory + "/" + last_ingredient_file, 'r', encoding='utf8') as f:
            self.ingredientDict = json.load(f)

    def saveDiffFormatList(self, filePath):
        with open(filePath, 'w', encoding='utf8') as jsonFile:
            json.dump(self.diffFormatList, jsonFile, indent="\t", ensure_ascii=False)

    def loadDiffFormatList(self, saveDirectory):
        file_list = os.listdir(saveDirectory)
        file_list_diff = [file for file in file_list if file.startswith("diff_format")]
        last_diff_file = file_list_diff[-1]

        with open(saveDirectory + "/" + last_diff_file, 'r', encoding='utf8') as f:
            self.diffFormatList = json.load(f)

def createFolder(path):
    import os

    try:
        if not os.path.exists(path):
            os.makedirs(path)
        return path
    except OSError:
        print('Error: Creating directory. ' + path)
        return None